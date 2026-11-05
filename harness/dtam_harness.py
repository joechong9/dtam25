#!/usr/bin/env python3
"""DTAM-MY harness: mechanical enforcement of the DTAM working method.

Turns the prose non-negotiables of `dtam-working-method` into checks that run
automatically (Claude Code hooks, CI) instead of relying on the agent's memory.

Checks
  drift        static EN/BM/ZH/TA forbidden strings (harness/drift_rules.json)
  constants    parametric drift vs harness/dtam_constants.json (GCP, total n,
               pilot n, supervisor names)
  parity       translation parity across en/bm/zh/ta dictionaries in HTML apps
  omr          OMR geometry constants vs the canonical layout
  manifest     dtam_manifest.json health, byte-identical duplicates, broken links
  sync         generated rule/model blocks inside apps match the source files

Commands
  check [FILES...] [--no-baseline] [--json] [--strict]
  baseline --write                  record current findings as the accepted baseline
  sync [FILES...] [--write]         regenerate DTAM_RULES blocks (repo apps, or any FILES given,
                                    e.g. the Report Assembler in PostGrad Work)
  status                            short summary (used by the SessionStart hook)
  hook post-edit | hook stop        Claude Code hook entry points (JSON on stdin)

Python 3.8+ standard library only. Exit codes: 0 ok, 1 new errors, 2 hook block.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HARNESS_DIR = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or HARNESS_DIR.parent).resolve()
CONSTANTS_PATH = HARNESS_DIR / "dtam_constants.json"
RULES_PATH = HARNESS_DIR / "drift_rules.json"
BASELINE_PATH = HARNESS_DIR / "baseline.json"
MANIFEST_PATH = ROOT / "dtam_manifest.json"

SEV_ORDER = {"error": 0, "warn": 1, "info": 2}
LANG_CODES = {"en", "bm", "ms", "zh", "ta"}
SYNC_BEGIN = "/* DTAM_RULES:BEGIN"
SYNC_END = "/* DTAM_RULES:END */"


# ───────────────────────────── utilities ─────────────────────────────

def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def rel(path) -> str:
    p = Path(path).resolve()
    try:
        return p.relative_to(ROOT).as_posix()
    except ValueError:
        return p.as_posix()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def line_of(text: str, idx: int) -> int:
    return text.count("\n", 0, idx) + 1


def finding(rule, severity, file, line, match, message):
    match = re.sub(r"\s+", " ", match).strip()
    if len(match) > 120:
        match = match[:117] + "..."
    return {"rule": rule, "severity": severity, "file": file, "line": line,
            "match": match, "message": message}


def fingerprint(f: dict) -> str:
    return f"{f['rule']}|{f['file']}|{f['match']}"


def py_flags(flags: str) -> int:
    out = 0
    if "i" in flags:
        out |= re.IGNORECASE
    return out


class Ctx:
    """Loaded configuration shared by all checks."""

    def __init__(self):
        self.constants = load_json(CONSTANTS_PATH)
        self.rules_doc = load_json(RULES_PATH)
        self.rules = [
            dict(r, rx=re.compile(r["pattern"], py_flags(r.get("flags", ""))))
            for r in self.rules_doc["rules"]
        ]
        self.neg_rx = re.compile(self.rules_doc["negation_pattern"], re.IGNORECASE)
        self.neg_window = int(self.rules_doc.get("negation_window", 60))
        self.allow_token = self.rules_doc.get("inline_allow_token", "dtam-harness: allow")
        self.exts = set(self.rules_doc["scan_extensions"])
        self.exclude = self.rules_doc["scan_exclude"]

    def is_excluded(self, relpath: str) -> bool:
        for ex in self.exclude:
            if ex.endswith("/"):
                if relpath.startswith(ex) or f"/{ex}" in f"/{relpath}":
                    return True
            elif relpath == ex or relpath.endswith("/" + ex):
                return True
        return False

    def targets(self, files=None, external=False):
        if files:
            paths = [Path(f).resolve() for f in files]
        else:
            paths = [p for p in ROOT.rglob("*") if p.is_file()]
        out = []
        for p in sorted(paths):
            if not p.exists() or p.suffix.lower() not in self.exts:
                continue
            r = rel(p)
            if (r.startswith("/") and not external) or (not r.startswith("/") and self.is_excluded(r)):
                continue
            out.append(p)
        return out


LINE_DOC_RX = re.compile(r"fabricat|hard-block|forbidden|FORBIDDEN_RULES|drift rule", re.IGNORECASE)


def suppressed(ctx: Ctx, text: str, start: int, end: int, rule_id: str) -> bool:
    """Negation context or inline allow comment on the same line."""
    pre = text[max(0, start - ctx.neg_window):end]  # window before + the match itself
    if ctx.neg_rx.search(pre):
        return True
    ls = text.rfind("\n", 0, start) + 1
    le = text.find("\n", end)
    line = text[ls: le if le != -1 else len(text)]
    # Rule-carrying documentation ("Known fabrications to hard-block: ..."). Short lines
    # only, so a giant single-line HTML bundle cannot hide real usage.
    if len(line) <= 400 and LINE_DOC_RX.search(line):
        return True
    tok = ctx.allow_token
    if tok in line:
        tail = line.split(tok, 1)[1]
        if rule_id in tail[:200] or "all" in tail[:20].lower():
            return True
    return False


# ───────────────────────────── drift (static) ─────────────────────────────

def check_drift(ctx: Ctx, path: Path, text: str):
    out = []
    r = rel(path)
    spans = []  # spans already reported at a higher severity (avoid double counting)
    for rule in sorted(ctx.rules, key=lambda x: SEV_ORDER[x["severity"]]):
        for m in rule["rx"].finditer(text):
            if any(s <= m.start() < e or s < m.end() <= e for s, e in spans):
                continue
            if suppressed(ctx, text, m.start(), m.end(), rule["id"]):
                continue
            spans.append((m.start(), m.end()))
            out.append(finding(rule["id"], rule["severity"], r, line_of(text, m.start()),
                               m.group(0), rule["fix"]))
    return out


# ───────────────────────────── constants (parametric) ─────────────────────

GCP_RX = re.compile(r"(\d{1,2})\s*/\s*22\b")
GCP_CTX_RX = re.compile(r"GCP|ICH|E6|compliance|patuh|合规|合規|இணக்க", re.IGNORECASE)
THRESH_RX = re.compile(r"(≥|>=|<=|≤|<|>|at least|below|above|minimum|threshold)\s*$", re.IGNORECASE)
TOTAL_RX = re.compile(r"\b(total|overall|jumlah|keseluruhan)\b[^\n.;<]{0,40}?\bn\s*=\s*(\d{2,4})\b|(总|總|மொத்த)[^\n.;<]{0,20}?\bn\s*=\s*(\d{2,4})\b",
                      re.IGNORECASE)
PILOT_RX = re.compile(r"\b(pilot|rintis)\b[^\n.;<]{0,30}?\bn\s*=\s*(\d{1,4})\b|(试点|試點|முன்னோட்ட)[^\n.;<]{0,20}?\bn\s*=\s*(\d{1,4})\b",
                      re.IGNORECASE)
APPROVAL_CLAIM_RX = re.compile(
    r"reviewed\s+and\s+approved|UREC[- ]approved|approved\s+by\s+(?:the\s+)?(?:UTAR|UREC)"
    r"|ethics\s+approval\s+(?:has\s+been\s+|was\s+)?(?:granted|obtained)"
    r"|disemak\s+dan\s+diluluskan|diluluskan\s+oleh\s+(?:Jawatankuasa|UTAR|UREC)|Diluluskan\s+UTAR\s+UREC"
    r"|审查和批准|审核并批准|已(?:获|经)[^。待]{0,20}批准|UREC批准(?!待)"
    r"|அங்கீகரிக்கப்பட்டது|UREC\s+அங்கீகாரம்(?!\s*நிலுவை)",
    re.IGNORECASE)
RANK_BEFORE_RX = re.compile(r"(Assoc\.?\s*Prof|A/Prof|Associate\s+Prof|Prof\.?\s*Madya|PM\.?)[^<\n]{0,14}$", re.IGNORECASE)
RANK_AFTER_RX = re.compile(r"^[^\n]{0,40}?(Associate\s+Prof|Assoc\.?\s*Prof|Prof(?:esor|\.)?\s*Madya|副教授|இணைப்\s*பேராசிரியர்|இணை)", re.IGNORECASE)
PENDING_CLAIM_RX = re.compile(
    r"UREC\s+Approval\s+Pending|approval\s+(?:is\s+)?pending|(?:UREC\s+)?ethics\s+approval[^.<\n]{0,80}?is\s+pending"
    r"|pending\s+(?:UREC\s+)?ethics\s+clearance|awaiting\s+submission|not\s+(?:yet\s+)?submitted"
    r"|no\s+data\s+(?:are|will\s+be)\s+collected\s+(?:until|before)"
    r"|UTAR/UREC/2025|Pending\s+UREC\s+submission|Pending\s+ethics\s+submission"
    r"|Ethics\s+Reference\s+Number\s*-\s*pending|pending\s+ethics\s+ref(?:erence)?\s+number"
    r"|Kelulusan\s+UTAR\s+UREC\s+Tertunda|Kelulusan\s+masih\s+belum|menunggu\s+kelulusan(?:\s+etika)?"
    r"|belum\s+dikemukakan|kelulusan\s+belum\s+diterima|menunggu\s+nombor\s+rujukan\s+etika"
    r"|批准待定|尚待批准|正在等待[^。]{0,40}批准|等待\s*UREC\s*伦理审批|尚未提交|审批中|等待伦理参考号"
    r"|அங்கீகாரம்\s+(?:இன்னும்\s+)?நிலுவையில்|நெறிமுறை\s+ஒப்புதல்\s+வரை|இன்னும்\s+சமர்ப்பிக்கப்படவில்லை"
    r"|நெறிமுறை\s+குறிப்பு\s+எண்[^.\n]{0,40}நிலுவை",
    re.IGNORECASE)
SUP_RX = re.compile(
    r"(Main Supervisor|Co-Supervisor|Supervisor|Penyelia(?:\s+Utama|\s+Bersama)?)\s*[:：]\s*"
    r"((?:Assoc\.?\s*Prof\.?|A/Prof\.?|Prof\.?|Ir\.?|Dr\.?|Ts\.?)\s*)*"
    r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})")


def check_constants(ctx: Ctx, path: Path, text: str):
    c = ctx.constants
    r = rel(path)
    out = []
    gcp = c["gcp"]["score"]
    for m in GCP_RX.finditer(text):
        val = int(m.group(1))
        if val == gcp:
            continue
        pre = text[max(0, m.start() - 60):m.start()]
        if not GCP_CTX_RX.search(pre + text[m.end():m.end() + 30]):
            continue
        if THRESH_RX.search(pre[-14:]) or suppressed(ctx, text, m.start(), m.end(), "GCP_DRIFT"):
            continue
        out.append(finding("GCP_DRIFT", "error", r, line_of(text, m.start()), m.group(0),
                           f"GCP score drift. Canonical GCP audit score is {gcp}/22 "
                           f"(thresholds ≥20/22 and <17/22 are allowed)."))
    total = c["sample"]["total_n"]
    for m in TOTAL_RX.finditer(text):
        val = int(m.group(2) or m.group(4))
        if re.search(r"pilot|rintis|试点|試點", m.group(0), re.IGNORECASE):
            continue  # "n=370 total · pilot n=70": the n belongs to the pilot clause
        if val != total and not suppressed(ctx, text, m.start(), m.end(), "TOTAL_N_DRIFT"):
            out.append(finding("TOTAL_N_DRIFT", "error", r, line_of(text, m.start()), m.group(0),
                               f"Total sample drift. Canonical total n={total}."))
    allowed = set(c["sample"]["pilot_allowed_numbers"])
    for m in PILOT_RX.finditer(text):
        val = int(m.group(2) or m.group(4))
        if val not in allowed and not suppressed(ctx, text, m.start(), m.end(), "STALE_PILOT_N"):
            out.append(finding("STALE_PILOT_N", "warn", r, line_of(text, m.start()), m.group(0),
                               f"Pilot n drift. Canonical pilot n={c['sample']['pilot_n']} "
                               f"(42 urban + 28 rural; 45 effective completers). Per-group targets "
                               f"of n=50 are legitimate - confirm context."))
    eth = c.get("ethics", {})
    if eth.get("status") == "pending":
        for m in APPROVAL_CLAIM_RX.finditer(text):
            if suppressed(ctx, text, m.start(), m.end(), "ETHICS_STATUS"):
                continue
            out.append(finding("ETHICS_STATUS", "error", r, line_of(text, m.start()), m.group(0),
                               "Claims UREC approval, but ethics status is 'pending' "
                               "(dtam_constants.json ethics.status). State that approval is pending; "
                               "participant-facing text must not overstate ethics status."))
    elif eth.get("status") == "approved":
        for m in PENDING_CLAIM_RX.finditer(text):
            if suppressed(ctx, text, m.start(), m.end(), "ETHICS_STATUS"):
                continue
            out.append(finding("ETHICS_STATUS", "error", r, line_of(text, m.start()), m.group(0),
                               "Says ethics approval is pending or not yet submitted, or uses a placeholder "
                               "reference, but UREC has approved the study (dtam_constants.json ethics.status; "
                               "canonical source: PostGrad Work CLAUDE.md §1). Use approved wording."))
    for name in (c["supervisors"]["main"], c["supervisors"]["co"]):
        for m in re.finditer(re.escape(name), text):
            before = text[max(0, m.start() - 22):m.start()]
            after = text[m.end():m.end() + 60]
            if RANK_BEFORE_RX.search(before) or RANK_AFTER_RX.search(after):
                continue
            if suppressed(ctx, text, m.start(), m.end(), "SUPERVISOR_TITLE"):
                continue
            out.append(finding("SUPERVISOR_TITLE", "warn", r, line_of(text, m.start()),
                               before.strip()[-12:] + " " + name,
                               "Supervisor named without academic rank. Use 'Assoc. Prof. Dr. Kwan Ban Hoe' / "
                               "'Assoc. Prof. Ir. Dr. Goh Choon Hian' (or state the rank right after the name)."))
    names = [c["supervisors"]["main"], c["supervisors"]["co"]]
    keys = {" ".join(n.split()[:2]).lower() for n in names}
    for m in SUP_RX.finditer(text):
        name = m.group(3)
        if " ".join(name.split()[:2]).lower() in keys:
            continue
        if suppressed(ctx, text, m.start(), m.end(), "SUPERVISOR_NAME"):
            continue
        out.append(finding("SUPERVISOR_NAME", "error", r, line_of(text, m.start()), m.group(0),
                           f"Supervisor name not canonical. Main: {names[0]}; Co: {names[1]}. "
                           f"Never infer names from templates."))
    return out


# ───────────────────────────── JS object literal parser ───────────────────

IDENT_RX = re.compile(r"[A-Za-z_$][\w$]*|\d+")
OPAQUE = object()


class JSParseError(Exception):
    pass


class JSObj:
    """Minimal JS object-literal parser: recovers key structure, values opaque."""

    def __init__(self, s: str):
        self.s = s
        self.n = len(s)

    def ws(self, i):
        s, n = self.s, self.n
        while i < n:
            c = s[i]
            if c in " \t\r\n":
                i += 1
            elif s.startswith("//", i):
                j = s.find("\n", i)
                i = n if j < 0 else j + 1
            elif s.startswith("/*", i):
                j = s.find("*/", i + 2)
                i = n if j < 0 else j + 2
            else:
                break
        return i

    def skip_str(self, i):
        s, n = self.s, self.n
        q = s[i]
        i += 1
        while i < n:
            c = s[i]
            if c == "\\":
                i += 2
                continue
            if q == "`" and c == "$" and i + 1 < n and s[i + 1] == "{":
                i = self.skip_balanced(i + 1)
                continue
            if c == q:
                return i + 1
            if q != "`" and c == "\n":
                return i + 1
            i += 1
        return n

    def skip_balanced(self, i):
        s, n = self.s, self.n
        depth = 0
        while i < n:
            i = self.ws(i)
            if i >= n:
                break
            c = s[i]
            if c in "\"'`":
                i = self.skip_str(i)
                continue
            if c in "{[(":
                depth += 1
            elif c in "}])":
                depth -= 1
                if depth == 0:
                    return i + 1
            i += 1
        return n

    def opaque(self, i):
        s, n = self.s, self.n
        while i < n:
            i = self.ws(i)
            if i >= n:
                break
            c = s[i]
            if c in ",}]":
                return i
            if c in "\"'`":
                i = self.skip_str(i)
            elif c in "{[(":
                i = self.skip_balanced(i)
            else:
                i += 1
        return n

    def value(self, i):
        i = self.ws(i)
        if i < self.n and self.s[i] == "{":
            return self.obj(i)
        if i < self.n and self.s[i] == "[":
            return OPAQUE, self.skip_balanced(i)
        return OPAQUE, self.opaque(i)

    def obj(self, i):
        s, n = self.s, self.n
        if s[i] != "{":
            raise JSParseError("expected {")
        i += 1
        out = {}
        guard = 0
        while True:
            guard += 1
            if guard > 200000:
                raise JSParseError("runaway")
            i = self.ws(i)
            if i >= n:
                raise JSParseError("unterminated object")
            c = s[i]
            if c == "}":
                return out, i + 1
            if c == ",":
                i += 1
                continue
            if s.startswith("...", i):
                _, i = OPAQUE, self.opaque(i + 3)
                continue
            if c in "\"'`":
                end = self.skip_str(i)
                key = s[i + 1:end - 1]
                i = end
            elif c == "[":
                i = self.skip_balanced(i)
                key = None
            else:
                m = IDENT_RX.match(s, i)
                if not m:
                    raise JSParseError(f"bad key at {i}")
                key = m.group(0)
                i = m.end()
            i = self.ws(i)
            if i < n and s[i] == ":":
                val, i = self.value(i + 1)
            elif i < n and s[i] == "(":
                i = self.skip_balanced(i)
                i = self.ws(i)
                if i < n and s[i] == "{":
                    i = self.skip_balanced(i)
                val = OPAQUE
            else:
                val = OPAQUE
            if key is not None:
                out[key] = val


def leaf_paths(obj, prefix=""):
    for k, v in obj.items():
        p = f"{prefix}{k}"
        if isinstance(v, dict) and v:
            yield from leaf_paths(v, p + ".")
        else:
            yield p


DECL_RX = re.compile(r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*\{")


def lang_dicts(text: str):
    """Yield (name, line, {lang: set(paths)}) for i18n dictionaries in a file."""
    parser = JSObj(text)
    for m in DECL_RX.finditer(text):
        try:
            obj, _ = parser.obj(m.end() - 1)
        except (JSParseError, IndexError, RecursionError):
            continue
        keys = set(obj)
        langs = keys & LANG_CODES
        if len(langs) < 2 or len(langs) / max(len(keys), 1) < 0.75:
            continue
        per = {lg: set(leaf_paths(obj[lg])) if isinstance(obj[lg], dict) else set() for lg in langs}
        yield m.group(1), line_of(text, m.start()), per


def check_parity(ctx: Ctx, path: Path, text: str):
    if path.suffix.lower() not in (".html", ".htm", ".js"):
        return []
    r = rel(path)
    out = []
    for name, line, per in lang_dicts(text):
        ref = per["en"] if "en" in per else set().union(*per.values())
        for lg, paths in sorted(per.items()):
            for key in sorted(ref - paths):
                out.append(finding("TRANSLATION_PARITY", "warn", r, line, f"{name}.{lg}.{key}",
                                   f"Key '{key}' missing from {name}.{lg} "
                                   f"(present in {'en' if 'en' in per else 'another language'}). "
                                   f"Participants in this language see a fallback or a blank."))
    return out


# ───────────────────────────── OMR geometry ───────────────────────────────

def check_omr(ctx: Ctx, path: Path, text: str):
    if path.suffix.lower() not in (".html", ".htm", ".js", ".py") or "COL_A_W" not in text:
        return []
    g = ctx.constants["omr_geometry_mm"]
    r = rel(path)
    vals = {}
    for name in ("PAGE_W", "PAGE_H", "LM", "TM", "BM", "COL_A_W", "BSPC", "BR"):
        m = re.search(rf"\b{name}\s*=\s*(-?\d+(?:\.\d+)?)\b", text)
        if m:
            vals[name] = (float(m.group(1)), m.start())
    gm = re.search(r"\bCOL_B_X\s*=\s*LM\s*\+\s*COL_A_W\s*\+\s*(\d+(?:\.\d+)?)", text)
    if gm:
        vals["GAP"] = (float(gm.group(1)), gm.start())
    expect = {"PAGE_W": g["PAGE_W"], "PAGE_H": g["PAGE_H"], "LM": g["LM"], "TM": g["TM"],
              "BM": g["BM"], "COL_A_W": g["A_W"], "BSPC": g["BSPC"], "BR": g["BR"], "GAP": g["GAP"]}
    out = []
    for k, exp in expect.items():
        if k in vals and abs(vals[k][0] - exp) > 1e-6:
            out.append(finding("OMR_GEOMETRY", "error", r, line_of(text, vals[k][1]),
                               f"{k}={vals[k][0]:g}", f"OMR layout drift: {k} must be {exp} mm "
                               f"(dtam_constants.json omr_geometry_mm). F1-F6 regression rules."))
    if all(k in vals for k in ("PAGE_W", "LM", "COL_A_W", "GAP")):
        bw = vals["PAGE_W"][0] - (vals["LM"][0] + vals["COL_A_W"][0] + vals["GAP"][0]) - g["RM"]
        if abs(bw - g["B_W"]) > 1e-6:
            out.append(finding("OMR_GEOMETRY", "error", r, line_of(text, vals["COL_A_W"][1]),
                               f"COL_B_W={bw:g}", f"Derived column B width must be {g['B_W']} mm."))
    return out


# ───────────────────────────── manifest / links / duplicates ──────────────

LINK_RX = re.compile(
    r"""(?:href|src)\s*=\s*["']([^"'#?:]+\.html?)[#?"']|(?:window\.open|location(?:\.href)?\s*=|location\.replace)\s*\(?\s*["']([^"'#?:]+\.html?)""")


def check_repo(ctx: Ctx):
    out = []
    html = sorted(p for p in ROOT.glob("*.htm*") if p.is_file())
    manifest = None
    if MANIFEST_PATH.exists():
        manifest = load_json(MANIFEST_PATH)
    else:
        out.append(finding("MANIFEST_MISSING", "error", "dtam_manifest.json", 1, "missing",
                           "No manifest: canonical file versions cannot be resolved."))
    registered, aliases = set(), {}
    if manifest:
        for app in manifest.get("apps", []):
            can = app["canonical"]
            registered.add(can)
            if not (ROOT / can).exists():
                out.append(finding("MANIFEST_MISSING_CANONICAL", "error", "dtam_manifest.json", 1, can,
                                   f"Canonical file for app '{app['id']}' does not exist."))
            for a in app.get("aliases", []):
                aliases[a] = can
                registered.add(a)
                ap = ROOT / a
                if not ap.exists():
                    out.append(finding("ALIAS_MISSING", "warn", "dtam_manifest.json", 1, a,
                                       f"Alias of {can} is listed but missing (old links will 404)."))
                    continue
                t = read_text(ap)
                if ap.stat().st_size > 4096 or can not in t:
                    out.append(finding("ALIAS_NOT_STUB", "error", a, 1, a,
                                       f"Alias must be a small redirect stub to {can}, not a full copy "
                                       f"(full copies drift apart)."))
    for p in html:
        if p.name not in registered:
            out.append(finding("UNREGISTERED_HTML", "warn", p.name, 1, p.name,
                               "HTML app not registered in dtam_manifest.json."))
    digests = defaultdict(list)
    for p in html:
        if p.name in aliases:
            continue
        digests[hashlib.md5(p.read_bytes()).hexdigest()].append(p.name)
    for names in digests.values():
        if len(names) > 1:
            for dup in names[1:]:
                out.append(finding("DUPLICATE_FILE", "error", dup, 1, f"{dup} == {names[0]}",
                                   "Byte-identical duplicate. Keep one canonical file; make the "
                                   "other a redirect stub registered as an alias."))
    for p in html:
        text = read_text(p)
        for m in LINK_RX.finditer(text):
            target = m.group(1) or m.group(2)
            if "/" in target or "${" in target:
                continue
            if not (ROOT / target).exists():
                out.append(finding("BROKEN_LINK", "error", p.name, line_of(text, m.start()), target,
                                   f"Link target '{target}' does not exist."))
    return out


# ───────────────────────────── generated blocks (sync) ────────────────────

def generated_block(ctx: Ctx) -> str:
    rules = [{"id": r["id"], "sev": r["severity"], "label": r.get("label", r["id"]), "p": r["pattern"],
              "f": r.get("flags", "") + "u", "fix": r["fix"]}
             for r in ctx.rules_doc["rules"] if r["severity"] in ("error", "warn")]
    llm = ctx.constants["llm"]
    lines = [
        f"{SYNC_BEGIN} - generated by harness/dtam_harness.py sync --write from "
        f"harness/drift_rules.json + harness/dtam_constants.json. Do not edit by hand. */",
        "const DTAM_DRIFT_RULES = " + json.dumps(rules, ensure_ascii=False) + ";",
        "const DTAM_CHAT_MODEL_DEFAULT = " + json.dumps(llm["chat_model"]) + ";",
        "const DTAM_CHAT_MODEL_OPTIONS = " + json.dumps(llm["chat_model_options"]) + ";",
        SYNC_END,
    ]
    return "\n".join(lines)


def sync_targets():
    cands = sorted(ROOT.glob("*.htm*")) + sorted((ROOT / "proxy").glob("*.js"))
    return [p for p in cands if p.is_file() and SYNC_BEGIN in read_text(p)]


def check_sync(ctx: Ctx):
    out = []
    want = generated_block(ctx)
    for p in sync_targets():
        t = read_text(p)
        s = t.index(SYNC_BEGIN)
        e = t.index(SYNC_END, s) + len(SYNC_END)
        if t[s:e] != want:
            out.append(finding("RULES_OUT_OF_SYNC", "error", p.name, line_of(t, s), "DTAM_RULES block",
                               "Generated rule/model block differs from the source files. "
                               "Run: python3 harness/dtam_harness.py sync --write"))
    return out


def do_sync(ctx: Ctx, write: bool, files=None) -> int:
    """Sync generated blocks. FILES may be anywhere (e.g. apps in PostGrad Work);
    without FILES, the repo's own apps and proxy are discovered automatically."""
    want = generated_block(ctx)
    changed = missing = 0
    if files:
        targets = []
        for f in files:
            p = Path(f).resolve()
            if not p.is_file():
                print(f"not found: {f}")
                missing += 1
            elif SYNC_BEGIN not in read_text(p) or SYNC_END not in read_text(p):
                print(f"no DTAM_RULES markers: {f} (add '{SYNC_BEGIN} */' and '{SYNC_END}' "
                      f"inside a <script> block first)")
                missing += 1
            else:
                targets.append(p)
    else:
        targets = sync_targets()
    for p in targets:
        t = read_text(p)
        s = t.index(SYNC_BEGIN)
        e = t.index(SYNC_END, s) + len(SYNC_END)
        if t[s:e] != want:
            changed += 1
            print(f"{'updated' if write else 'out of sync'}: {rel(p)}")
            if write:
                p.write_text(t[:s] + want + t[e:], encoding="utf-8")
    if not changed and not missing:
        print("all generated blocks in sync")
    return 1 if (missing or (changed and not write)) else 0


# ───────────────────────────── orchestration ──────────────────────────────

FILE_CHECKS = (check_drift, check_constants, check_parity, check_omr)


def mask_generated(text: str) -> str:
    """Blank generated rule blocks (they contain the rule patterns themselves)."""
    s = text.find(SYNC_BEGIN)
    while s != -1:
        e = text.find(SYNC_END, s)
        if e == -1:
            break
        e += len(SYNC_END)
        text = text[:s] + re.sub(r"[^\n]", " ", text[s:e]) + text[e:]
        s = text.find(SYNC_BEGIN, e)
    return text


def run_checks(ctx: Ctx, files=None, repo_checks=True, external=False):
    findings = []
    for p in ctx.targets(files, external):
        text = mask_generated(read_text(p))
        for chk in FILE_CHECKS:
            findings.extend(chk(ctx, p, text))
    if repo_checks:
        findings.extend(check_repo(ctx))
        findings.extend(check_sync(ctx))
    findings.sort(key=lambda f: (SEV_ORDER[f["severity"]], f["file"], f["line"], f["rule"]))
    return findings


def load_baseline() -> dict:
    if BASELINE_PATH.exists():
        return load_json(BASELINE_PATH).get("findings", {})
    return {}


def new_vs_baseline(findings, baseline, files_scope=None):
    """Return findings exceeding the baseline count for their fingerprint."""
    counts = Counter(fingerprint(f) for f in findings)
    seen = Counter()
    new = []
    for f in findings:
        fp = fingerprint(f)
        seen[fp] += 1
        allowed = baseline.get(fp, {}).get("count", 0)
        if seen[fp] > allowed:
            new.append(f)
    fixed = []
    for fp, meta in baseline.items():
        if files_scope is not None and meta["file"] not in files_scope:
            continue
        if counts.get(fp, 0) < meta["count"]:
            fixed.append((fp, meta["count"] - counts.get(fp, 0)))
    return new, fixed


def summarize(findings, limit=40, indent="  "):
    lines = []
    groups = defaultdict(list)
    for f in findings:
        groups[(f["severity"], f["rule"], f["file"])].append(f)
    for n, ((sev, rule, file), items) in enumerate(
            sorted(groups.items(), key=lambda kv: (SEV_ORDER[kv[0][0]], kv[0]))):
        if n >= limit:
            lines.append(f"{indent}... {len(groups) - limit} more groups")
            break
        first = items[0]
        where = ", ".join(str(i["line"]) for i in items[:6]) + (" ..." if len(items) > 6 else "")
        sample = "; ".join(sorted({i["match"] for i in items})[:3])
        lines.append(f"{indent}[{sev.upper()}] {rule} x{len(items)} in {file} (line {where}): {sample}")
        lines.append(f"{indent}    fix: {first['message']}")
    return "\n".join(lines)


def write_baseline(findings):
    data = {}
    for f in findings:
        if f["severity"] == "info":
            continue
        fp = fingerprint(f)
        if fp not in data:
            data[fp] = {"rule": f["rule"], "severity": f["severity"], "file": f["file"],
                        "match": f["match"], "count": 0, "status": "open"}
        data[fp]["count"] += 1
    doc = {
        "_comment": ("Accepted findings (ratchet). Entries are KNOWN OPEN DEFECTS, not exemptions: "
                     "CI and hooks fail only on findings beyond these counts, so nothing new gets in "
                     "while these are fixed. After fixing, run `python3 harness/dtam_harness.py "
                     "baseline --write` to tighten the ratchet."),
        "version": 1,
        "findings": dict(sorted(data.items())),
    }
    BASELINE_PATH.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return len(data), sum(v["count"] for v in data.values())


def cmd_check(args) -> int:
    ctx = Ctx()
    files = args.files or None
    findings = run_checks(ctx, files, repo_checks=not files, external=args.external)
    baseline = {} if (args.no_baseline or args.external) else load_baseline()
    scope = {rel(f) for f in files} if files else None
    new, fixed = new_vs_baseline([f for f in findings if f["severity"] != "info"], baseline, scope)
    if args.json:
        print(json.dumps({"findings": findings, "new": new, "fixed": fixed}, ensure_ascii=False, indent=1))
    else:
        sev = Counter(f["severity"] for f in findings)
        print(f"DTAM harness: {len(findings)} findings "
              f"({sev['error']} error, {sev['warn']} warn, {sev['info']} info); "
              f"{len(new)} new vs baseline")
        if new:
            print("\nNEW (not in baseline):")
            print(summarize(new))
        open_ = [f for f in findings if f not in new and f["severity"] == "error"]
        if open_ and not args.quiet:
            print(f"\nOPEN DEFECTS carried in baseline ({len(open_)} error findings) - still need fixing:")
            print(summarize(open_, limit=25))
        if fixed:
            print(f"\nFIXED since baseline: {sum(n for _, n in fixed)} finding(s). "
                  f"Tighten with: python3 harness/dtam_harness.py baseline --write")
    new_err = [f for f in new if f["severity"] == "error"]
    if new_err or (args.strict and new):
        return 1
    return 0


def cmd_baseline(args) -> int:
    ctx = Ctx()
    findings = run_checks(ctx)
    if not args.write:
        print("dry run; pass --write to record the baseline")
        return 0
    n, total = write_baseline(findings)
    print(f"baseline written: {n} fingerprints, {total} findings -> {rel(BASELINE_PATH)}")
    return 0


def cmd_status(_args) -> int:
    ctx = Ctx()
    c = ctx.constants
    base = load_baseline()
    open_err = sum(v["count"] for v in base.values() if v["severity"] == "error")
    open_warn = sum(v["count"] for v in base.values() if v["severity"] == "warn")
    rules = Counter()
    for v in base.values():
        if v["severity"] == "error":
            rules[v["rule"]] += v["count"]
    print("DTAM-MY harness active (harness/). Canonical constants come from "
          "harness/dtam_constants.json, never from memory:")
    print(f"  total n={c['sample']['total_n']} | pilot n={c['sample']['pilot_n']} "
          f"(42 urban + 28 rural, 45 completers) | GCP {c['gcp']['score']}/22 | "
          f"supervisors {c['supervisors']['main']} (main), {c['supervisors']['co']} (co) | "
          f"{c['study']['faculty']}")
    print(f"  Canonical file versions: dtam_manifest.json (a higher _vN is NOT canonical).")
    print(f"  Open defects in baseline: {open_err} error, {open_warn} warn"
          + (f" - top: {', '.join(f'{k} x{v}' for k, v in rules.most_common(4))}" if rules else ""))
    print("  Edits are drift-scanned automatically; run `python3 harness/dtam_harness.py check` "
          "before declaring work done.")
    return 0


def read_hook_input() -> dict:
    try:
        raw = sys.stdin.read()
        return json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, OSError):
        return {}


def cmd_hook(args) -> int:
    data = read_hook_input()
    ctx = Ctx()
    if args.event == "post-edit":
        ti = data.get("tool_input") or {}
        fp = ti.get("file_path") or ti.get("notebook_path")
        if not fp:
            return 0
        p = Path(fp)
        if not p.is_absolute():
            p = (ROOT / p)
        if not p.exists() or not ctx.targets([str(p)]):
            return 0
        findings = [f for f in run_checks(ctx, [str(p)], repo_checks=False) if f["severity"] != "info"]
        new, _ = new_vs_baseline(findings, load_baseline(), {rel(p)})
        errors = [f for f in new if f["severity"] == "error"]
        warns = [f for f in new if f["severity"] == "warn"]
        if errors:
            sys.stderr.write(
                f"DTAM harness BLOCK: your edit to {rel(p)} introduced {len(errors)} drift error(s). "
                f"Fix them at source now (dtam-working-method §3, §4):\n{summarize(errors, 15)}\n")
            if warns:
                sys.stderr.write(f"Also {len(warns)} warning(s) to confirm:\n{summarize(warns, 10)}\n")
            return 2
        if warns:
            msg = (f"DTAM harness: edit to {rel(p)} raised {len(warns)} warning(s) needing human "
                   f"confirmation - flag them to YZ if not clearly legitimate:\n{summarize(warns, 10)}")
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                                     "additionalContext": msg}}))
        return 0
    if args.event == "stop":
        if data.get("stop_hook_active"):
            return 0
        findings = [f for f in run_checks(ctx) if f["severity"] != "info"]
        new, _ = new_vs_baseline(findings, load_baseline())
        errors = [f for f in new if f["severity"] == "error"]
        if errors:
            sys.stderr.write(
                f"DTAM harness: {len(errors)} new error(s) vs baseline remain in the repo. Fix them, "
                f"or report them plainly to YZ as unresolved before finishing:\n{summarize(errors, 15)}\n")
            return 2
        return 0
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("files", nargs="*")
    c.add_argument("--no-baseline", action="store_true")
    c.add_argument("--json", action="store_true")
    c.add_argument("--strict", action="store_true", help="also fail on new warnings")
    c.add_argument("--quiet", action="store_true", help="omit the open-defects listing")
    c.add_argument("--external", action="store_true",
                   help="allow FILES outside the repo (e.g. synced skills); no baseline")
    c.set_defaults(fn=cmd_check)
    b = sub.add_parser("baseline")
    b.add_argument("--write", action="store_true")
    b.set_defaults(fn=cmd_baseline)
    s = sub.add_parser("sync")
    s.add_argument("files", nargs="*", help="files to sync (may be outside the repo); default: discover in repo")
    s.add_argument("--write", action="store_true")
    s.set_defaults(fn=lambda a: do_sync(Ctx(), a.write, a.files or None))
    st = sub.add_parser("status")
    st.set_defaults(fn=cmd_status)
    h = sub.add_parser("hook")
    h.add_argument("event", choices=["post-edit", "stop"])
    h.set_defaults(fn=cmd_hook)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
