# Deploying DTAM-MY to the study server

This runbook updates a server that already serves an older version of the apps. Read it all before starting; allow about an hour.

## 0. Before you deploy: ethics check

Several participant-facing changes in this release are recorded as **pending amendments** in the protocol (Research Suite, protocol §11 log):

- Policy-Maker item `pol2` reworded to the Health White Paper (2023)
- Consent notices: 7-year retention; speech-to-text disclosure
- Part C: speech-to-text opt-in; distress/AE/SAE record form
- Four new Elderly items (time since stroke, rehabilitation setting, travel distance, telerehab received)

The four new Elderly items are **hidden by default** (`ENABLE_PENDING_ITEMS = false`). Show them only after the UREC amendment and CVI validation are approved; see step 3.

Confirm with UREC whether the other changes may be used with participants before the amendment is approved. Until then, you can deploy for staff testing only.

## 1. Build

On any machine with Node.js 18+ and internet access:

```bash
git clone https://github.com/joechong9/dtam25.git
```

```bash
cd dtam25/deploy && npm ci && npm run build
```

The output is `deploy/dist/`:

- JSX is pre-compiled, so the Babel compiler is not shipped and `'unsafe-eval'` is removed (except in the OMR scanner, where OpenCV's WebAssembly needs it).
- React, ReactDOM and Chart.js are self-hosted in `dist/vendor/` with SRI hashes.
- OpenCV.js is self-hosted if the build machine can reach docs.opencv.org; otherwise it loads from there. `BUILD_INFO.txt` says which.

To skip the build, upload the repository-root HTML files instead. They work as they are, but load libraries from jsDelivr and compile JSX in the browser.

## 2. Preserve your server's own settings

The repository is public and does not contain your server's settings. Before replacing files, check the live copies for local edits:

```bash
grep -n "API_ENDPOINT\|API_KEY\|connect-src" /path/to/webroot/*.html
```

The usual edits to re-apply in `deploy/dist/`, never in the public repository:

| File | Setting | Why |
|---|---|---|
| `telerehab_questionnaire_app_v2.html` | `DTAM_CONFIG.API_ENDPOINT` (and `API_KEY`) | Sends each response to your server as well as saving it locally |
| same file, `<meta http-equiv="Content-Security-Policy">` | `connect-src` must list your endpoint's origin | Otherwise the browser blocks the POST |
| `admin_portal_v2.html` | Nothing to edit for the Claude assistant: the proxy URL is entered in Settings and stored per browser. Its CSP already allows `https://*.workers.dev`; if your proxy uses another domain, add it to `connect-src` | Keeps the API key off the browser |

## 3. Optional: show the pending-validation items

Only after approval:

```bash
cd deploy && DTAM_ENABLE_PENDING_ITEMS=1 npm run build
```

`BUILD_INFO.txt` then reads `pending-validation items: ENABLED`.

## 4. Back up, then upload

1. **Export data on every field device first.** In the Admin Portal, export the survey CSV, interview CSV/JSON and OMR JSON. Browser data survives an update only if the site stays at exactly the same address (same scheme, host and path).
2. Back up the current web root:

   ```bash
   tar czf dtam25-backup-$(date +%Y%m%d-%H%M).tgz -C /path/to/webroot .
   ```

3. Upload the contents of `deploy/dist/` into the web root, keeping the same file names. The redirect pages `index_v2.html`, `omr_scanner_v2.html` and `telerehab_dashboard.html` keep old links and QR codes working.
4. Add the security headers:
   - **Apache:** copy `deploy/headers/apache.htaccess` to `/path/to/webroot/.htaccess` (needs `mod_headers`).
   - **nginx:** copy `deploy/headers/nginx.conf` to `/etc/nginx/snippets/dtam25-headers.conf`, `include` it in the server block, then run `nginx -t && systemctl reload nginx`.
   - Leave the HSTS line out until HTTPS works for the whole domain.

## 5. Smoke test (about 15 minutes)

Open the browser developer console (F12) on each page; there should be no red errors or "Refused to…" messages.

| Page | Check |
|---|---|
| `index.html` | Loads; switch EN/BM/中文/தமிழ்; the chatbot answers "what is fhir" |
| `telerehab_questionnaire_app_v2.html` | Complete one Elderly test response; the report shows scores. On a test device, remove it afterwards with Admin Portal → Export → Clear Survey Data (this deletes **all** survey data in that browser, so never do it on a field device) |
| `admin_portal_v2.html` | Sign in; the test response appears; Settings → Registration Tokens loads |
| `telerehab_dashboard_v2.html` | Charts render; the OMR tab shows the embedded scanner |
| `omr_scanner.html?sheet=ELDERLY` | The Elderly sheet is preselected; the camera prompt appears when you start a capture |
| `partc_interview_v2.html` | Speech-to-text is off by default; switching it on adds the notice to the consent screen |
| `verbal_interview_ui_v2.html` | Loads; the consent notice says 7 years |
| `DTAM_MY_Research_Suite.html` | GCP 19/22; the protocol §11 log lists the pending amendments |
| Response headers | `curl -sI https://YOUR-HOST/index.html` shows `Content-Security-Policy: frame-ancestors 'self'…` and `X-Content-Type-Options: nosniff` |

On field tablets, reload each page once. HTML is served with `Cache-Control: no-cache`, so later updates arrive automatically.

## 6. Roll back

```bash
cd /path/to/webroot && rm -rf ./* && tar xzf /path/to/dtam25-backup-YYYYMMDD-HHMM.tgz
```

Browser data on the devices is not affected by a rollback.

## 7. Known limits of this release

- Without `API_ENDPOINT` (step 2), data stays in each device's browser. Collect on study-owned devices and export regularly. Architecture spec findings F-05, F-08 and F-10 track the move to a central Malaysian-hosted store.
- Admin accounts and registration tokens are per browser.
