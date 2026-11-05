# Claude key proxy (optional, recommended)

The admin portal's Claude assistant can call the API in two ways:

| Mode | How | Risk |
|---|---|---|
| Direct (default when no proxy URL is set) | The browser holds the API key and calls `api.anthropic.com` with `anthropic-dangerous-direct-browser-access` | Anyone with access to the browser or a malicious extension can read the key |
| **Proxy** | The browser calls this Worker; the key lives only in a Worker secret | Key never reaches the browser |

## Deploy (Cloudflare Workers, free tier is enough)

```bash
npm install -g wrangler
cd proxy
wrangler login
wrangler deploy claude-proxy-worker.js --name dtam-claude-proxy --compatibility-date 2026-10-01
wrangler secret put ANTHROPIC_API_KEY --name dtam-claude-proxy      # paste the key
wrangler secret put PORTAL_TOKEN --name dtam-claude-proxy           # optional shared token
```

Then in the Cloudflare dashboard, set the Worker variable `ALLOWED_ORIGINS` to the
origin that serves the portal, for example `https://joechong9.github.io`.

In the admin portal, open **Settings → API Keys** and fill in:

1. **Key proxy URL**: `https://dtam-claude-proxy.<account>.workers.dev`
2. **Proxy access token**: only if you set `PORTAL_TOKEN`
3. Leave the API key field empty.

The portal's Content-Security-Policy already allows `https://*.workers.dev`. If you
host the proxy on another domain, add it to `connect-src` in `admin_portal_v2.html`.

## What the Worker enforces

- Only origins in `ALLOWED_ORIGINS`, only `POST /v1/messages`.
- Model allowlist and default from `harness/dtam_constants.json` (`llm` section),
  copied into the Worker by `python3 harness/dtam_harness.py sync --write`. CI fails
  if the copy drifts.
- Only `model`, `max_tokens`, `system`, `messages`, `output_config` are forwarded;
  `max_tokens` is capped at 4096.

Add a Cloudflare rate-limiting rule on the Worker route if the portal is public.
