# DTAM-MY web apps (dtam25)

Static, single-file HTML apps for CHONG Yu Zheng's UTAR PhD telerehabilitation
study (DTAM-MY), served from the repository root. No build step.

This file is deliberately thin. Rules live in the `dtam-*` skills; numbers live in
`harness/dtam_constants.json`; enforcement lives in `harness/`.

## Before you change anything

1. Load the `dtam-working-method` skill, plus the task skill if one covers the work
   (for example `dtam-html-design-standard` for any HTML restyle).
2. Resolve the canonical file in `dtam_manifest.json`. A higher `_vN` in a filename
   does not make a file canonical. Aliases (`index_v2.html`, `omr_scanner_v2.html`,
   `telerehab_dashboard.html`) are redirect stubs: never edit content into them.
3. Take every canonical number, name and constant from `harness/dtam_constants.json`,
   never from memory or from another app.
4. `harness/dtam_constants.json` mirrors the canonical facts table (§1) of PostGrad
   Work's `CLAUDE.md`, which lives in a private repository and wins on any
   disagreement. The apps here are an **older public snapshot**: when a fact is in
   doubt, check §1, never the majority of files in this repo. (In November 2026 the
   UREC wording here was "corrected" from approved to pending, and a later session
   built on that, because most files here were stale; §1 records the study as
   approved.)
5. This repo is **public**. Never copy files or facts from PostGrad Work wholesale:
   port only the specific strings needed, and only with the PI's agreement. Never
   contact details, server details or data. Open defects that need private facts are
   recorded in `harness/baseline.json` with status `open-needs-private-facts`.

## The harness (runs automatically)

- **SessionStart** prints the canonical constants and the open-defect count.
- **PostToolUse** drift-scans every file you edit. A new error blocks with the fix
  text: correct it at source before moving on. Warnings need YZ's confirmation.
- **Stop** blocks if the repo has new errors relative to `harness/baseline.json`.
- **CI** (`.github/workflows/harness.yml`) runs the same checks plus the test suite.

Manual commands:

```bash
python3 harness/dtam_harness.py check            # all checks vs baseline
python3 harness/dtam_harness.py check FILE...    # specific files
python3 harness/dtam_harness.py sync --write     # regenerate rule/model blocks in apps
python3 harness/dtam_harness.py baseline --write # tighten the ratchet after fixing
python3 -m unittest discover -s harness/tests -v # harness self-tests
(cd harness/tests/browser && npm ci && npm test)  # browser tests for every app (Playwright)
```

`harness/baseline.json` lists known open defects, not exemptions. Shrink it; never
grow it to make a check pass. If a finding is a legitimate named exception, add an
inline `dtam-harness: allow RULE_ID` comment on that line and say why.

## Changing a rule or a constant

- New forbidden string: add it to `harness/drift_rules.json` (EN + BM/ZH/TA forms),
  add should-hit and should-not-hit cases to `harness/tests/test_harness.py`, then
  run `sync --write`.
- New constant value: edit `harness/dtam_constants.json`, run `check`, and fix what
  it flags.
- Default chat model: `llm.chat_model` in the constants file, then `sync --write`.

## Delivery

Targeted fixes only: change exactly what was flagged. For anything rendered, check
it in a browser (Playwright is available) before calling it done. Close with a short
outcome summary and state any unresolved findings plainly.
