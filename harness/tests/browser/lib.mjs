// Shared helpers for the DTAM-MY browser tests (node --test).
// Pages are opened from the repository either over file:// or a local HTTP server. Requests to the
// CDNs the apps use (jsDelivr npm, docs.opencv.org; cdnjs for older pages) are answered from the pinned
// local copies in node_modules, so the tests are deterministic and work offline. The page's own CSP and
// Subresource Integrity checks still apply: jsDelivr serves npm files unchanged, so the local copies
// match the integrity hashes, and a CSP or SRI mismatch still fails the test.
import { chromium } from 'playwright';
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
export const REPO = path.resolve(HERE, '..', '..', '..');
const NM = path.join(HERE, 'node_modules');

const CDN_FILES = {
  'react.production.min.js': 'react/umd/react.production.min.js',
  'react-dom.production.min.js': 'react-dom/umd/react-dom.production.min.js',
  'babel.min.js': '@babel/standalone/babel.min.js',
  'chart.umd.min.js': 'chart.js/dist/chart.umd.js',
  'opencv.js': '@techstark/opencv-js/dist/opencv.js',
};

// Browser notices that are not app errors.
const BENIGN = [/frame-ancestors/];

/**
 * @param {'file'|'http'} mode
 * @param {{ block?: RegExp }} [opts]  block: CDN requests to abort (e.g. to simulate Chart.js being offline)
 */
export async function setup(mode = 'file', opts = {}) {
  let base = 'file://' + REPO + '/';
  let server = null;
  if (mode === 'http') {
    server = http.createServer((req, res) => {
      const p = path.join(REPO, decodeURIComponent(req.url.split(/[?#]/)[0]));
      if (!p.startsWith(REPO)) { res.writeHead(403); return res.end(); }
      fs.readFile(p, (err, data) => {
        if (err) { res.writeHead(404); return res.end(); }
        res.writeHead(200, { 'content-type': p.endsWith('.html') ? 'text/html; charset=utf-8' : 'application/octet-stream' });
        res.end(data);
      });
    });
    await new Promise(r => server.listen(0, '127.0.0.1', r));
    base = `http://127.0.0.1:${server.address().port}/`;
  }
  const browser = await chromium.launch(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {});
  const ctx = await browser.newContext();
  const js = file => ({ path: file, contentType: 'application/javascript', headers: { 'access-control-allow-origin': '*' } });
  await ctx.route(/^https:\/\/(cdnjs\.cloudflare\.com|docs\.opencv\.org|cdn\.jsdelivr\.net)\//, route => {
    const url = route.request().url();
    if (opts.block && opts.block.test(url)) return route.abort();
    // jsDelivr: https://cdn.jsdelivr.net/npm/<pkg>@<version>/<path>  ->  node_modules/<pkg>/<path>
    const m = url.match(/^https:\/\/cdn\.jsdelivr\.net\/npm\/((?:@[^/]+\/)?[^@/]+)@([^/]+)\/(.+)$/);
    if (m) {
      const [, pkg, version, file] = m;
      const pinned = JSON.parse(fs.readFileSync(path.join(NM, pkg, 'package.json'), 'utf8')).version;
      if (pinned !== version) throw new Error(`${pkg}@${version} requested but ${pinned} is pinned in package.json`);
      return route.fulfill(js(path.join(NM, pkg, file)));
    }
    const local = CDN_FILES[url.split('/').pop()];
    if (local) return route.fulfill(js(path.join(NM, local)));
    return route.abort();
  });
  // Anthropic API is never called for real in tests.
  await ctx.route('https://api.anthropic.com/**', route => route.fulfill({
    status: 200, contentType: 'application/json', headers: { 'access-control-allow-origin': '*' },
    body: JSON.stringify({ content: [{ type: 'text', text: 'REPLY-OK' }], stop_reason: 'end_turn' }),
  }));
  return {
    base, ctx,
    async close() { await browser.close(); if (server) server.close(); },
  };
}

/** Open a page and collect page errors and console errors (minus benign notices). */
export async function open(env, file, { acceptDialogs = true } = {}) {
  const page = await env.ctx.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push('pageerror: ' + e.message));
  page.on('console', m => {
    if (m.type() === 'error' && !BENIGN.some(rx => rx.test(m.text()))) errors.push('console: ' + m.text().slice(0, 300));
  });
  if (acceptDialogs) page.on('dialog', d => d.accept());
  if (file) await page.goto(env.base + file);
  return { page, errors };
}

/** Fake Web Speech API: window.__sr.emit(text) delivers a final result. */
export const FAKE_SPEECH = () => {
  class FakeSR {
    constructor() { window.__sr = this; }
    start() { setTimeout(() => this.onstart && this.onstart(), 0); }
    stop() { setTimeout(() => this.onend && this.onend(), 300); }
    abort() {}
    emit(text) { this.onresult && this.onresult({ resultIndex: 0, results: [{ 0: { transcript: text }, isFinal: true, length: 1 }] }); }
  }
  window.SpeechRecognition = FakeSR;
};

export const CANONICAL_PAGES = [
  'index.html', 'telerehab_questionnaire_app_v2.html', 'telerehab_dashboard_v2.html', 'admin_portal_v2.html',
  'omr_scanner.html', 'partc_interview_v2.html', 'verbal_interview_ui_v2.html', 'DTAM_MY_Research_Suite.html',
];
