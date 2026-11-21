# Proposed patches to the account-level `dtam-*` skills

**Status (2026-11-05): corrected copies of 11 skills were delivered as
`dtam_skills_corrected.zip`, ready to upload.** They apply Patches 1, 3, 4 and 5
below, plus two additions found later: the UREC approval status and supervisor
ranks. **Correction (2026-11-21): the UREC wording in that zip ("pending, never
state approval") is wrong. PostGrad Work CLAUDE.md §1 records the study as
approved, and `harness/dtam_constants.json` `ethics.status` is `approved`. Do not
upload those 11 skills until the UREC line is fixed, and re-check any already
uploaded.** Patch 2 concerns files in PostGrad Work
(Bundle Compiler, Report Assembler, Citation Auditor, Loop Engine), which are not
in this repository, so it remains to be done there.

The skills are synced from the claude.ai account, so a repository session cannot
edit them. Apply these in the skill editor (or with the `skill-creator` skill). They
finish recommendation 3 (one source of truth) and the portability fix.

## Audit result (2026-11-05)

`python3 harness/dtam_harness.py check --external <skills>/dtam-*/SKILL.md` found
**no numeric drift**: every skill agrees with `harness/dtam_constants.json`. The only
hits are lines that document the forbidden strings themselves, which are expected
named exceptions. The risk is not drift today but duplication: the same constants
are restated in 12 skills, CLAUDE.md (PostGrad Work), and 3 library-app copies.

## Patch 1: replace the restated constants in every §0 guardrail block

In each of the 11 skills that carry `## §0 Guardrails`, replace item 4:

```diff
-4. CONSTANTS: Total n=370; pilot n=70 (42 urban + 28 rural, 45 completers); GCP 19/22; A/Prof Dr Kwan Ban Hoe (main) · A/Prof. Ir. Dr Goh Choon Hian (co) · LKC FES.
+4. CONSTANTS: take every number and name from `dtam_constants.json` (repo: harness/; PostGrad Work: same file) — never from memory or another skill. If that file is unavailable, use CLAUDE.md §1. Run the harness `check` before delivering.
```

Keep the §0 block itself. Its duplication is intentional, because it makes each
skill safe when loaded alone. Only the numbers move out.

Apply the same change to `dtam-working-method` §1.1, §3.3 and §5, and to the
"Canonical constants" footer of `dtam-loop-engine`.

## Patch 2: one drift-rule source for the Loop Engine and library apps

`dtam-library-apps` says the validation core is "duplicated across three files and
must change in all three". Point all three at `drift_rules.json` instead:

- Bundle Compiler (Python): load `drift_rules.json` at start-up instead of the
  inline `FORBIDDEN_RULES` list. The patterns are already Python-compatible.
- Report Assembler and Citation Auditor (HTML): add the
  `/* DTAM_RULES:BEGIN */ /* DTAM_RULES:END */` markers and let
  `dtam_harness.py sync --write` fill them, as `admin_portal_v2.html` now does.
  The files can live outside this repo, so from PostGrad Work run:
  `python3 <dtam25>/harness/dtam_harness.py sync --write DTAM_MY_Report_Assembler_v1.0.html DTAM_MY_Citation_Auditor_v1.0.html`
  (without `--write` it reports whether they are in sync and exits 1 if not).
- Loop Engine: register a verifier that shells out to
  `dtam_harness.py check --json FILES` and maps `new` findings to LES findings.

Then edit the skill's "Extension recipes" to read: *add the rule to
drift_rules.json, add fixtures to harness/tests, run sync --write*.

## Patch 3: portability (Cowork/macOS-only assumptions)

| Skill | Line | Change |
|---|---|---|
| `dtam-council` | "Canonical file: /Users/yuchong/Documents/..." | Express it relative to the project root (`PostGrad Work/council_of_advisors.html`) and resolve it through `dtam_manifest.json`. |
| `dtam-council` | "After every edit: call mcp__cowork__update_artifact" | Add: "only in Cowork; in Claude Code, publish with the Artifact tool or skip." |
| `dtam-council` | `window.cowork.askClaude` "is the only CDN-free LLM path" | Add the proxy path (`proxy/claude-proxy-worker.js`) as the non-Cowork option. |
| `dtam-manual-compiler`, `dtam-doc-formatter` | "PostGrad Work is the default" | State the fallback when the folder is absent (repository root), so cloud sessions do not silently write elsewhere. |

## Patch 4: wire the harness into `dtam-working-method` §7

Add a final checklist item:

```diff
+11. Did `python3 harness/dtam_harness.py check` report 0 new findings? If the
+    PostToolUse hook blocked an edit, did I fix the cause at source instead of
+    working around it?
```

## Patch 5: architecture-doc agent count

`dtam-architecture-doc` says "Specialist agent layer — 8 agents" but lists 7
(Ethics & Protocol, Questionnaire & OMR, Literature & Framework, Statistical &
Analytics, App & FHIR Dev, QA & Data Warehouse, ML Pipeline). Either name the eighth
or change the count to 7. This needs your decision.

## Patch 6: stale UREC wording in four synced skills (found 2026-11-21)

The study is approved (`ethics.status`; PostGrad Work CLAUDE.md §1). These synced
skills still treat it as pre-submission. `check --external` now catches all four
(new rules in `PENDING_CLAIM_RX`). Paths are inside each skill; line numbers are from
the copies synced on 2026-11-21. The approval reference is not stored here (public
repo), so the replacements point to the approval letter; YZ supplies the reference.

**1. `telerehab-questionnaire/assets/telerehab_questionnaire_app.html`, line 945**
(participant-facing consent, section 8). It says the study is approved but gives an
invented placeholder reference that does not match `^U/SERC/\d+\([A-Z]\)-\d+/\d{4}$`.
Replace the second sentence with one of:

- Reference known: `Reference: <YZ to supply, shape U/SERC/n(X)-n/yyyy>.`
- Reference not yet released for this copy: delete the `Reference: ...` sentence.

Do not leave a placeholder reference in a participant-facing page.

**2. `telerehab-research-protocol/references/gcp-audit-full.md`, lines 28-31 and 203**
(E6 2.1 Ethics Committee Approval).

Replace the Protocol response and Status with:

```
**Protocol response**: UTAR UREC approval obtained (reference per the approval letter);
the ethics reference number appears in all participant-facing documents; no data
collection outside the approved protocol; amendment log maintained for all subsequent
changes.
**Status**: <YZ to set the marker, see note>
```

Replace line 203 (the sentence that says both open items resolve in the normal course
of submission) with: `△ Items are procedural (pre-registration) and do not
represent substantive gaps.` **Note for YZ:** moving E6 2.1 from △ to ✓ changes the
audit tally (the file and `SKILL.md` quote 20/22 = 91% with advisory corrections;
the constants say 19/22). I have not recalculated it; that is your call.

**3. `dtam-architecture-doc/references/arch-content.md`, line 213** (status table).
Change the status cell of the UREC ethics submission row from pending to
`✓ Approved`. The Q3 2026 date cell is a plan date; replace it with the actual
approval date only if YZ gives it.

**4. `telerehab-research-protocol/SKILL.md`, lines 126 and 130** (mild, generic wording).

- Line 126: drop the ethics reference number from the list of pending examples,
  leaving `(e.g., pre-registration)`.
- Line 130: change `acceptable for UREC submission with explanation of △ items` to
  `acceptable with explanation of △ items`.

**Also seen, not UREC (needs YZ):** `check --external` warns `STALE_PILOT_N` in
`telerehab-research-protocol/SKILL.md` (lines 160, 173, 247) and
`references/gcp-audit-full.md` (line 171). Per-group pilot targets of n=50 are
legitimate; canonical pilot n=70 (42 + 28, 45 completers). Review each in context.
