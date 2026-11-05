# dtam25

DTAM-MY web apps for the UTAR PhD study *Development of Digital Healthcare
Telerehabilitation Technology Assessments Model and System for Enhancement of
Elderly Quality-of-Life*. Each app is a self-contained HTML file; open
`index.html` to start. Canonical files and their aliases are listed in
`dtam_manifest.json`.

There is no build step and no server code: open a page directly (double-click) or serve the folder statically.
React, Babel, Chart.js and OpenCV.js load from CDNs, so the first load needs an internet connection.

## Apps

| File | Purpose |
|---|---|
| `index.html` | Public landing page with FAQ chatbot |
| `telerehab_questionnaire_app_v2.html` | Participant questionnaire (EN/BM/ZH/TA), 5 stakeholder groups, local scoring |
| `telerehab_dashboard_v2.html` | Research dashboard over saved questionnaire responses |
| `admin_portal_v2.html` | Password-gated admin portal: progress, exports, OMR import, registration tokens, optional Claude assistant |
| `omr_scanner.html` | Paper OMR sheet scanner (OpenCV perspective correction) |
| `partc_interview_v2.html` | Part C qualitative interview with in-browser speech-to-text |
| `verbal_interview_ui_v2.html` | Verbal interview prototype (**speech-to-text is simulated**) |
| `DTAM_MY_Research_Suite.html` | Project overview: phases, protocol, framework matrix |

`index_v2.html`, `omr_scanner_v2.html` and `telerehab_dashboard.html` are redirect stubs to the canonical files
above (see `dtam_manifest.json`); never edit content into them. Deep links into the scanner work in both forms:
`omr_scanner.html?sheet=ELDERLY` or `omr_scanner.html#ELDERLY`.

## Deploying

Development needs no build step. For the study server, `deploy/` provides an optional hardened build (pre-compiled JSX with no `'unsafe-eval'`, self-hosted libraries with SRI) and security-header snippets for Apache and nginx. See **`DEPLOY.md`** for the full runbook: ethics check, preserving server settings, backup, upload, smoke tests and rollback.

```bash
cd deploy && npm ci && npm run build   # output: deploy/dist/
```

## Shared browser storage (same origin)

| Key | Written by | Read by | Shape |
|---|---|---|---|
| `dtam_my_responses` (localStorage) | questionnaire | dashboard, admin portal | array of `ResponseRecord`: `{id, timestamp, group, lang, mode, answers, scores:{KEY:{value,…}}, meta:{lang}}` (`mode` is `digital`; OMR exports carry `mode: "paper"`, verbal exports `mode: "verbal"`; see `docs/DTAM_MY_Item_Crosswalk_v1.0.md`) |
| `dtam_my_interviews` (localStorage) | Part C interview; admin portal (session JSON import from other devices) | admin portal | array of `{id, group, interviewer, language, site, startedAt, endedAt, duration, recordedSecs, questions, answered, completed, incidents:[{type, recordedAt}]}`, metadata only, no transcripts or incident descriptions |
| `dtam_omr_scans` (localStorage) | admin portal (JSON import) | admin portal | array of OMR scanner exports `{participant_id, sheet, timestamp, scores, results}` |
| `dtam_admin_users_v2` (localStorage) | admin portal | admin portal | accounts with salted PBKDF2 password hashes |
| `dtam_reg_tokens` (localStorage) | admin portal (Settings) | admin portal (Create Account) | single-use registration tokens: SHA-256 hash, label, expiry, used/revoked state; the code itself is never stored |
| `dtam_partc_draft` (sessionStorage) | Part C interview | Part C interview | running interview draft; cleared when the tab closes |

`group` keys: `allied`, `caregiver`, `elderly`, `policy`, `public`. `lang` is the questionnaire language
(`en`/`bm`/`zh`/`ta`); `meta.lang` is only the browser locale. JSDoc typedefs for these shapes are in the
files that write them.

All of this lives in one browser profile on one device: export regularly (CSV/JSON) and clear data after export
according to the study's data-management plan.

CSV exports start with a UTF-8 byte-order mark so Excel shows Chinese and Tamil correctly (in R use
`read.csv(f, fileEncoding = "UTF-8-BOM")` or `readr::read_csv`). Text cells beginning with `=`, `+`, `-` or `@`
are prefixed with `'` so spreadsheets do not run them as formulas; plain numbers are unchanged.

What leaves the device: the Part C and verbal interview apps transcribe speech with the browser's speech
service (Google in Chrome, Microsoft in Edge), and the admin assistant sends typed messages plus aggregate
counts to Anthropic's API. Both are outside Malaysia; the consent text and the admin portal say so. Registration tokens can therefore only be redeemed on the device
where they were issued.

## Harness

`harness/` enforces the DTAM working method mechanically:

| Piece | What it does |
|---|---|
| `harness/dtam_constants.json` | Single source of truth for sample sizes, GCP score, supervisors, OMR geometry, chat model |
| `harness/drift_rules.json` | Forbidden strings in EN/BM/ZH/TA, with fix text |
| `harness/dtam_harness.py` | Drift, constants, translation-parity, OMR-geometry and manifest checks; baseline ratchet; rule sync; hook entry points |
| `harness/baseline.json` | Known open defects. CI fails only on findings beyond these |
| `harness/tests/` | Fixtures for every rule, plus parser, hook and proxy tests |
| `harness/tests/browser/` | Playwright tests for every app (file:// and HTTP), with the CDN libraries pinned locally |
| `.claude/settings.json` | Claude Code hooks: status at session start, scan on every edit, gate on stop |
| `.github/workflows/harness.yml` | The same checks on every push and pull request |
| `proxy/` | Optional Cloudflare Worker that keeps the Anthropic key out of the browser |

```bash
python3 harness/dtam_harness.py check
python3 -m unittest discover -s harness/tests -v
node harness/tests/test_proxy.mjs
(cd harness/tests/browser && npm ci && npm test)
```

See `CLAUDE.md` for the agent workflow and `harness/SKILL_PATCHES.md` for the
matching changes proposed for the account-level `dtam-*` skills.
