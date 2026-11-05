# dtam25
DTAM 25

DTAM-MY (Digital Telerehabilitation Assessment Model – Malaysia) research suite: single-file browser apps.
There is no build step and no server code; open a page directly (double-click) or serve the folder statically.
React, Babel, Chart.js and OpenCV.js load from CDNs, so first load needs an internet connection.

## Apps

| File | Purpose |
|---|---|
| `index.html` / `index_v2.html` | Public landing page with FAQ chatbot (the two files are kept identical) |
| `telerehab_questionnaire_app_v2.html` | Participant questionnaire (EN/BM/ZH/TA), 5 stakeholder groups, local scoring |
| `telerehab_dashboard_v2.html` | Research dashboard over saved questionnaire responses |
| `admin_portal_v2.html` | Password-gated admin portal: progress, exports, OMR import, optional Claude assistant |
| `omr_scanner.html` / `omr_scanner_v2.html` | Paper OMR sheet scanner (OpenCV perspective correction); kept identical |
| `partc_interview_v2.html` | Part C qualitative interview with in-browser speech-to-text |
| `verbal_interview_ui_v2.html` | Verbal interview prototype (**speech-to-text is simulated**) |
| `DTAM_MY_Research_Suite.html` | Project overview: phases, protocol, framework matrix |

Both names of each duplicated page are linked from other pages, so keep the pairs in sync when editing.
Deep links into the scanner: `omr_scanner_v2.html?sheet=ELDERLY` or `omr_scanner.html#ELDERLY`.

## Shared browser storage (same origin)

| Key | Written by | Read by | Shape |
|---|---|---|---|
| `dtam_my_responses` (localStorage) | questionnaire | dashboard, admin portal | array of `ResponseRecord`: `{id, timestamp, group, lang, answers, scores:{KEY:{value,…}}, meta:{lang}}` |
| `dtam_my_interviews` (localStorage) | Part C interview | admin portal | array of `{id, group, interviewer, language, site, startedAt, endedAt, duration, recordedSecs, questions, answered, completed}`, metadata only, no transcripts |
| `dtam_omr_scans` (localStorage) | admin portal (JSON import) | admin portal | array of OMR scanner exports `{participant_id, sheet, timestamp, scores, results}` |
| `dtam_admin_users_v2` (localStorage) | admin portal | admin portal | accounts with salted PBKDF2 password hashes |
| `dtam_reg_tokens` (localStorage) | admin portal (Settings) | admin portal (Create Account) | single-use registration tokens: SHA-256 hash, label, expiry, used/revoked state; the code itself is never stored |
| `dtam_partc_draft` (sessionStorage) | Part C interview | Part C interview | running interview draft; cleared when the tab closes |

`group` keys: `allied`, `caregiver`, `elderly`, `policy`, `public`. `lang` is the questionnaire language
(`en`/`bm`/`zh`/`ta`); `meta.lang` is only the browser locale. JSDoc typedefs for these shapes are in the
files that write them.

All of this lives in one browser profile on one device: export regularly (CSV/JSON) and clear data after export
according to the study's data-management plan.
