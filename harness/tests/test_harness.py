"""Self-tests (evals) for the DTAM-MY harness.

Every rule has should-hit and should-not-hit fixtures so a rule change cannot
silently widen (false positives) or narrow (missed drift) what is caught.
Run: python3 -m unittest discover -s harness/tests -v
"""
import io
import json
import re
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import dtam_harness as h  # noqa: E402

CTX = h.Ctx()
FAKE = h.ROOT / "fixture.html"


def rules_hit(text, check=h.check_drift):
    return [f["rule"] for f in check(CTX, FAKE, text)]


class DriftRuleFixtures(unittest.TestCase):
    SHOULD_HIT = [
        ("NDHB_EN", "complies with the National Digital Health Blueprint 2023-2030"),
        ("NDHB_EN", "national digital health roadmap"),
        ("NDHB_ACRONYM", "<span>NDHB 2023</span>"),
        ("NDHB_ACRONYM", "aligned with NDHR goals"),
        ("NDHB_BM", "Pelan Hala Tuju Kesihatan Digital Kebangsaan 2023-2030"),
        ("NDHB_BM", "Pelan Induk Kesihatan Digital Nasional"),
        ("NDHB_ZH", "国家数字健康蓝图 2023-2030"),
        ("NDHB_ZH", "2023-2030年国家数字卫生蓝图提供足够指导"),
        ("NDHB_TA", "தேசிய டிஜிட்டல் சுகாதார வரைவு 2023-2030"),
        ("NDHB_TA", "தேசிய ඤிஜிட்டல் சுகாதார திட்டம் போதுமான"),  # corrupted glyph seen in the wild
        ("NDHB_TA_SHORT", "வரைவின் மூலோபாய திசை"),
        ("NDHB_EN_SHORT", "Does the Blueprint's strategic direction address"),
        ("NDHB_BM_SHORT", "Adakah hala tuju strategik Pelan Induk menangani"),
        ("NDHB_ZH_SHORT", "蓝图的战略方向是否专门针对"),
        ("LIM2017", "attrition of 20% (Lim et al., 2017)"),
        ("LIM2017", "Lim et al. 2017 reported"),
        ("FACULTY", "PhD candidate, FICT, UTAR"),
        ("KAPPA_ATTR", "kappa thresholds (Polit & Beck, 2006)"),
        ("WHITEBOOK", "the Healthcare White Book"),
        ("NEEDS_VERIFICATION", "attrition 20% [NEEDS VERIFICATION]"),
    ]
    SHOULD_NOT_HIT = [
        "Health White Paper (2023), MOH Malaysia, Command Paper No. 29 of 2023",
        "Kertas Putih Kesihatan (2023)",
        "LKC FES, Lee Kong Chian Faculty of Engineering and Science",
        "Abdullah, N. et al. (2021), IJERPH 18(14), 7216",
        "Polit, Beck & Owen (2007)",
        "Lim et al. (2019) examined stroke rehabilitation",
        "digital health services for older adults",
        "pelan rawatan kesihatan",
        "டிஜிட்டல் சுகாதார சேவைகளை",
        "சுகாதார வெள்ளை அறிக்கை (2023)",
        "《卫生白皮书》（2023）",
        "blueprints of the OMR sheet layout are in the appendix",
        "TAM (Davis, 1989); UTAUT2 (Venkatesh et al., 2012)",
        "NDHBX is not an acronym we use",
        # negation context: rule documentation, not usage
        "This is a known fabrication - never cite the National Digital Health Blueprint.",
        "replaced 'Lim et al. (2017)' with Abdullah et al. (2021)",
    ]

    def test_should_hit(self):
        for rule, text in self.SHOULD_HIT:
            with self.subTest(rule=rule, text=text):
                self.assertIn(rule, rules_hit(text))

    def test_should_not_hit(self):
        for text in self.SHOULD_NOT_HIT:
            with self.subTest(text=text):
                self.assertEqual(rules_hit(text), [])

    def test_inline_allow(self):
        text = "<li>FICT</li> <!-- dtam-harness: allow FACULTY (quoting the old letterhead) -->"
        self.assertEqual(rules_hit(text), [])
        text = "<li>FICT</li> <!-- dtam-harness: allow LIM2017 -->"
        self.assertEqual(rules_hit(text), ["FACULTY"])

    def test_short_form_not_double_counted(self):
        self.assertEqual(rules_hit("国家数字健康蓝图"), ["NDHB_ZH"])
        self.assertEqual(rules_hit("Pelan Induk Kesihatan Digital"), ["NDHB_BM"])

    def test_every_rule_has_a_fixture(self):
        covered = {r for r, _ in self.SHOULD_HIT}
        for rule in CTX.rules_doc["rules"]:
            self.assertIn(rule["id"], covered, f"add a should-hit fixture for {rule['id']}")

    def test_patterns_are_js_compatible(self):
        for rule in CTX.rules_doc["rules"]:
            self.assertNotIn("(?<", rule["pattern"], "lookbehind/named groups break JS")
            self.assertNotIn("(?P", rule["pattern"])


class ConstantsFixtures(unittest.TestCase):
    def hits(self, text):
        return rules_hit(text, h.check_constants)

    def test_gcp(self):
        self.assertEqual(self.hits("GCP compliance score: 18/22"), ["GCP_DRIFT"])
        self.assertEqual(self.hits("ICH E6(R2) GCP audit 22/22"), ["GCP_DRIFT"])
        self.assertEqual(self.hits("GCP compliance score: 19/22"), [])
        self.assertEqual(self.hits("ethics agent passes GCP at ≥20/22 and escalates <17/22"), [])
        self.assertEqual(self.hits("ZBI prorates if >=18/22 items answered"), [])
        self.assertEqual(self.hits("question 18/22 of the ZBI"), [])

    def test_total_n(self):
        self.assertEqual(self.hits("Total target: n=350 participants"), ["TOTAL_N_DRIFT"])
        self.assertEqual(self.hits("Total target: n = 370"), [])
        self.assertEqual(self.hits("Jumlah peserta n=370"), [])
        self.assertEqual(self.hits("n=370 total · pilot n=70 (42 urban + 28 rural)"), [])

    def test_pilot_n(self):
        self.assertEqual(self.hits("pilot study (n=50)"), ["STALE_PILOT_N"])
        self.assertEqual(self.hits("pilot n=70 (42 urban + 28 rural)"), [])
        self.assertEqual(self.hits("pilot n=45 effective completers"), [])
        self.assertEqual(self.hits("the pilot is NOT n=50"), [])
        self.assertEqual(self.hits("General Public (n=50)"), [])

    APPROVAL_CLAIMS = ["This study has been reviewed and approved by the UTAR UREC.",
                       "<strong>Ethics:</strong> UTAR UREC approved.",
                       "Kajian ini telah disemak dan diluluskan oleh Jawatankuasa Etika",
                       "'Diluluskan UTAR UREC'",
                       "本研究已经过伦理委员会审查和批准。",
                       "'UTAR UREC批准'",
                       "குழுவால் மதிப்பாய்வு செய்யப்பட்டு அங்கீகரிக்கப்பட்டது.",
                       "'UTAR UREC அங்கீகாரம்'"]
    PENDING_CLAIMS = ["Ethics approval from the UTAR University Research Ethics Committee (UREC) is pending, and no data will be collected until it is granted.",
                      "'UTAR UREC Approval Pending'",
                      "Reference: UTAR/UREC/2025 (pending).",
                      "Ethics Reference: [Pending UREC submission]",
                      "{desc:'Pending ethics submission'}",
                      "n=70 · pending ethics clearance (UREC)",
                      "📋 UTAR UREC ethics application — <b>awaiting submission</b>; approval pending",
                      "Three procedural items pending ethics ref number and MREC registration.",
                      "Kajian ini masih menunggu kelulusan etika daripada Jawatankuasa",
                      "📋 Permohonan etika UTAR UREC — <b>belum dikemukakan</b>",
                      "'Kelulusan UTAR UREC Tertunda'",
                      "本研究正在等待拉曼大学（UTAR）大学研究伦理委员会（UREC）的伦理批准",
                      "📋 UTAR UREC 伦理申请 — <b>尚未提交</b>",
                      "'UTAR UREC批准待定'",
                      "UREC நெறிமுறை விண்ணப்பம் — <b>இன்னும் சமர்ப்பிக்கப்படவில்லை</b>",
                      "'UTAR UREC அங்கீகாரம் நிலுவையில்'"]
    NEUTRAL = ["Available after UREC ethics clearance", "8. Ethics Approval",
               "MREC registration follows UREC approval", "⏳ Distribution planned for Phase 4 (pilot)",
               "✈ TestFlight — நிலுவையில்"]

    def _with_status(self, status):
        old = CTX.constants["ethics"]["status"]
        CTX.constants["ethics"]["status"] = status
        self.addCleanup(lambda: CTX.constants["ethics"].__setitem__("status", old))

    def test_ethics_status_pending_flags_approval_claims(self):
        self._with_status("pending")
        for t in self.APPROVAL_CLAIMS:
            with self.subTest(t=t):
                self.assertEqual(self.hits(t), ["ETHICS_STATUS"])
        for t in self.NEUTRAL:
            with self.subTest(t=t):
                self.assertEqual(self.hits(t), [])

    def test_ethics_status_approved_flags_pending_claims(self):
        self._with_status("approved")
        for t in self.PENDING_CLAIMS:
            with self.subTest(t=t):
                self.assertEqual(set(self.hits(t)), {"ETHICS_STATUS"})  # some sentences hold two pending phrases
        for t in self.APPROVAL_CLAIMS + self.NEUTRAL:
            with self.subTest(t=t):
                self.assertEqual(self.hits(t), [])

    def test_supervisor_title(self):
        self.assertEqual(self.hits("📧 Dr Kwan Ban Hoe — kwanbh@utar.edu.my"), ["SUPERVISOR_TITLE"])
        self.assertEqual(self.hits("<div>Ir Dr Goh Choon Hian</div>"), ["SUPERVISOR_TITLE"])
        self.assertEqual(self.hits("Assoc. Prof. Dr. Kwan Ban Hoe"), [])
        self.assertEqual(self.hits("A/Prof. Ir. Dr Goh Choon Hian"), [])
        self.assertEqual(self.hits("<b>Dr Kwan Ban Hoe</b><br>Associate Professor, LKC FES"), [])
        self.assertEqual(self.hits("<b>Dr Kwan Ban Hoe</b> — 副教授"), [])
        self.assertEqual(self.hits("<b>Ir Dr Goh Choon Hian</b> — Prof. Madya · Penyelia Bersama"), [])

    def test_supervisor(self):
        self.assertEqual(self.hits("Main Supervisor: Assoc. Prof. Dr. Tan Wei Ming"), ["SUPERVISOR_NAME"])
        self.assertEqual(self.hits("Main Supervisor: Assoc. Prof. Dr. Kwan Ban Hoe"), [])
        self.assertEqual(self.hits("Co-Supervisor: A/Prof. Ir. Dr Goh Choon Hian"), [])
        self.assertEqual(self.hits("Penyelia Utama: Assoc. Prof. Dr. Kwan Ban Hoe"), [])


class ParityFixtures(unittest.TestCase):
    def parity(self, js):
        return [f["match"] for f in h.check_parity(CTX, FAKE, f"<script>{js}</script>")]

    def test_missing_key_detected(self):
        js = """const T = {
          en: { title: "Hello", nested: { a: 'x', b: `y ${1 + 2}` } },
          bm: { title: 'Helo', nested: { a: 'x' } },   // b missing
          zh: { title: "你好", nested: { a: 'x', b: 'y' } },
          ta: { /* comment */ title: 'வணக்கம்', nested: { a: 'x', b: 'y' } },
        };"""
        self.assertEqual(self.parity(js), ["T.bm.nested.b"])

    def test_no_en_uses_union(self):
        js = "const Q_TRANS = { bm: {q1:'a', q2:'b'}, zh: {q1:'a', q2:'b'}, ta: {q1:'a'} };"
        self.assertEqual(self.parity(js), ["Q_TRANS.ta.q2"])

    def test_non_language_objects_ignored(self):
        js = "const CFG = { en: 1, url: 'x', mode: 'y', depth: 3 }; const X = {a:{b:1}};"
        self.assertEqual(self.parity(js), [])

    def test_strings_with_braces_and_quotes(self):
        js = r"""const T = { en: { a: "it's {not} a key: b", c: 'x' }, bm: { a: 'y', c: "}" } };"""
        self.assertEqual(self.parity(js), [])


class OmrFixtures(unittest.TestCase):
    GOOD = """const PAGE_W = 297, PAGE_H = 210;
const LM = 12, TM = 10, BM = 10
const COL_A_X = LM, COL_A_W = 154
const COL_B_X = LM + COL_A_W + 4
const BSPC = 8, BR = 2.6"""

    def omr(self, text):
        return [f["match"] for f in h.check_omr(CTX, FAKE, text)]

    def test_canonical_layout_passes(self):
        self.assertEqual(self.omr(self.GOOD), [])

    def test_margin_drift(self):
        self.assertIn("LM=14", self.omr(self.GOOD.replace("LM = 12", "LM = 14")))

    def test_gap_drift_breaks_column_b(self):
        found = self.omr(self.GOOD.replace("COL_A_W + 4", "COL_A_W + 6"))
        self.assertIn("GAP=6", found)
        self.assertIn("COL_B_W=113", found)

    def test_live_scanner_matches(self):
        p = h.ROOT / "omr_scanner.html"
        self.assertEqual(h.check_omr(CTX, p, h.read_text(p)), [])


class RatchetAndSync(unittest.TestCase):
    def test_ratchet_counts(self):
        f = h.finding("FACULTY", "error", "a.html", 1, "FICT", "x")
        base = {h.fingerprint(f): {"count": 1, "file": "a.html", "severity": "error"}}
        new, fixed = h.new_vs_baseline([f], base)
        self.assertEqual((new, fixed), ([], []))
        new, _ = h.new_vs_baseline([f, dict(f, line=9)], base)
        self.assertEqual(len(new), 1)
        _, fixed = h.new_vs_baseline([], base)
        self.assertEqual(fixed, [(h.fingerprint(f), 1)])

    def test_generated_block_compiles_and_is_deterministic(self):
        a, b = h.generated_block(CTX), h.generated_block(CTX)
        self.assertEqual(a, b)
        line = next(l for l in a.splitlines() if l.startswith("const DTAM_DRIFT_RULES"))
        rules = json.loads(line[len("const DTAM_DRIFT_RULES = "):-1])
        for r in rules:
            re.compile(r["p"])

    def test_sync_external_file(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            app = Path(d) / "DTAM_MY_Report_Assembler_v1.0.html"
            app.write_text("<script>\n/* DTAM_RULES:BEGIN */\n/* DTAM_RULES:END */\nrun();\n</script>",
                           encoding="utf-8")
            bare = Path(d) / "no_markers.html"
            bare.write_text("<script>run();</script>", encoding="utf-8")
            with redirect_stdout(io.StringIO()):
                self.assertEqual(h.main(["sync", str(app)]), 1)           # out of sync, dry run
                self.assertEqual(h.main(["sync", "--write", str(app)]), 0)
                self.assertEqual(h.main(["sync", str(app)]), 0)           # now in sync
                self.assertEqual(h.main(["sync", str(bare)]), 1)          # markers missing
            out = app.read_text(encoding="utf-8")
            self.assertIn("const DTAM_DRIFT_RULES = ", out)
            self.assertTrue(out.endswith("run();\n</script>"))

    def test_mask_generated(self):
        t = "a\n" + h.generated_block(CTX) + "\nNDHB"
        masked = h.mask_generated(t)
        self.assertEqual(masked.count("\n"), t.count("\n"))
        self.assertEqual(rules_hit(masked), ["NDHB_ACRONYM"])


class RepoIntegration(unittest.TestCase):
    """The live repo must pass the CI gate: no findings beyond the baseline."""

    @classmethod
    def setUpClass(cls):
        cls.findings = h.run_checks(CTX)

    def test_no_new_findings_vs_baseline(self):
        new, _ = h.new_vs_baseline([f for f in self.findings if f["severity"] != "info"],
                                   h.load_baseline())
        self.assertEqual(new, [], h.summarize(new))

    def test_structure_is_clean(self):
        bad = {"MANIFEST_MISSING", "MANIFEST_MISSING_CANONICAL", "ALIAS_NOT_STUB", "ALIAS_MISSING",
               "DUPLICATE_FILE", "BROKEN_LINK", "UNREGISTERED_HTML", "RULES_OUT_OF_SYNC", "OMR_GEOMETRY"}
        hits = [f for f in self.findings if f["rule"] in bad]
        self.assertEqual(hits, [], h.summarize(hits))


class Hooks(unittest.TestCase):
    def run_hook(self, event, payload):
        err, out = io.StringIO(), io.StringIO()
        with mock.patch("sys.stdin", io.StringIO(json.dumps(payload))), \
                redirect_stderr(err), redirect_stdout(out):
            code = h.main(["hook", event])
        return code, err.getvalue(), out.getvalue()

    def test_post_edit_blocks_new_error(self):
        tmp = h.ROOT / "_harness_hook_test.html"
        try:
            tmp.write_text("<p>Faculty: FICT</p>", encoding="utf-8")
            code, err, _ = self.run_hook("post-edit", {"tool_input": {"file_path": str(tmp)}})
            self.assertEqual(code, 2)
            self.assertIn("FACULTY", err)
            tmp.write_text("<p>Faculty: LKC FES</p>", encoding="utf-8")
            code, err, _ = self.run_hook("post-edit", {"tool_input": {"file_path": str(tmp)}})
            self.assertEqual((code, err), (0, ""))
        finally:
            tmp.unlink(missing_ok=True)

    def test_post_edit_warn_is_context_not_block(self):
        tmp = h.ROOT / "_harness_hook_test.md"
        try:
            tmp.write_text("pilot study (n=50)", encoding="utf-8")
            code, _, out = self.run_hook("post-edit", {"tool_input": {"file_path": str(tmp)}})
            self.assertEqual(code, 0)
            self.assertIn("STALE_PILOT_N", json.loads(out)["hookSpecificOutput"]["additionalContext"])
        finally:
            tmp.unlink(missing_ok=True)

    def test_post_edit_ignores_harness_files(self):
        code, err, _ = self.run_hook("post-edit", {"tool_input": {"file_path": str(h.RULES_PATH)}})
        self.assertEqual((code, err), (0, ""))

    def test_stop_hook_does_not_loop(self):
        code, _, _ = self.run_hook("stop", {"stop_hook_active": True})
        self.assertEqual(code, 0)

    def test_stop_hook_clean_repo(self):
        code, err, _ = self.run_hook("stop", {})
        self.assertEqual(code, 0, err)


if __name__ == "__main__":
    unittest.main()
