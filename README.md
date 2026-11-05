# dtam25

DTAM-MY web apps for the UTAR PhD study *Development of Digital Healthcare
Telerehabilitation Technology Assessments Model and System for Enhancement of
Elderly Quality-of-Life*. Each app is a self-contained HTML file; open
`index.html` to start. Canonical files and their aliases are listed in
`dtam_manifest.json`.

## Harness

`harness/` enforces the DTAM working method mechanically:

| Piece | What it does |
|---|---|
| `harness/dtam_constants.json` | Single source of truth for sample sizes, GCP score, supervisors, OMR geometry, chat model |
| `harness/drift_rules.json` | Forbidden strings in EN/BM/ZH/TA, with fix text |
| `harness/dtam_harness.py` | Drift, constants, translation-parity, OMR-geometry and manifest checks; baseline ratchet; rule sync; hook entry points |
| `harness/baseline.json` | Known open defects. CI fails only on findings beyond these |
| `harness/tests/` | Fixtures for every rule, plus parser, hook and proxy tests |
| `.claude/settings.json` | Claude Code hooks: status at session start, scan on every edit, gate on stop |
| `.github/workflows/harness.yml` | The same checks on every push and pull request |
| `proxy/` | Optional Cloudflare Worker that keeps the Anthropic key out of the browser |

```bash
python3 harness/dtam_harness.py check
python3 -m unittest discover -s harness/tests -v
node harness/tests/test_proxy.mjs
```

See `CLAUDE.md` for the agent workflow and `harness/SKILL_PATCHES.md` for the
matching changes proposed for the account-level `dtam-*` skills.
