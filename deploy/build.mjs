#!/usr/bin/env node
// DTAM-MY deployment build (optional). Development needs no build step: the apps in the repo root
// run as they are. This script produces a hardened copy for the study server in deploy/dist/:
//   1. JSX (<script type="text/babel">) is compiled ahead of time, so Babel is not shipped and
//      'unsafe-eval' is removed from the Content-Security-Policy (except where OpenCV's WebAssembly needs it).
//   2. React, ReactDOM and Chart.js are copied into dist/vendor/ from pinned npm packages and served
//      from the study server (same bytes and SRI hashes as the jsDelivr URLs in the source files).
//   3. OpenCV.js is downloaded into dist/vendor/ and pinned with an SRI hash when the build machine can
//      reach docs.opencv.org; otherwise the scanner keeps loading it from docs.opencv.org.
// Usage:  cd deploy && npm ci && npm run build
import { readFileSync, writeFileSync, mkdirSync, copyFileSync, rmSync, existsSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, '..');
const dist = join(here, 'dist');
const require = createRequire(import.meta.url);
const Babel = require('@babel/standalone');

const sri = buf => 'sha384-' + createHash('sha384').update(buf).digest('base64');
const esc = s => s.replace(/[.*+?^${}()|[\]\\/]/g, '\\$&');

// jsDelivr URL in the source files -> npm file to self-host
const VENDOR = {
  'https://cdn.jsdelivr.net/npm/react@18.2.0/umd/react.production.min.js': 'react/umd/react.production.min.js',
  'https://cdn.jsdelivr.net/npm/react-dom@18.2.0/umd/react-dom.production.min.js': 'react-dom/umd/react-dom.production.min.js',
  'https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.js': 'chart.js/dist/chart.umd.js',
};
const BABEL_URL = 'https://cdn.jsdelivr.net/npm/@babel/standalone@7.23.2/babel.min.js';
const OPENCV_URL = 'https://docs.opencv.org/4.8.0/opencv.js';

async function main() {
  const manifest = JSON.parse(readFileSync(join(root, 'dtam_manifest.json'), 'utf8'));
  rmSync(dist, { recursive: true, force: true });
  mkdirSync(join(dist, 'vendor'), { recursive: true });

  // Vendor files (verify the hash the source files expect)
  const vendored = {};
  for (const [url, rel] of Object.entries(VENDOR)) {
    const buf = readFileSync(join(here, 'node_modules', rel));   // read directly: package "exports" hide umd/ paths
    const name = rel.split('/').pop();
    writeFileSync(join(dist, 'vendor', name), buf);
    vendored[url] = { path: `vendor/${name}`, integrity: sri(buf) };
  }

  // OpenCV.js: best effort
  let opencv = null;
  try {
    const res = await fetch(OPENCV_URL);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const buf = Buffer.from(await res.arrayBuffer());
    writeFileSync(join(dist, 'vendor', 'opencv-4.8.0.js'), buf);
    opencv = { path: 'vendor/opencv-4.8.0.js', integrity: sri(buf) };
    console.log(`OpenCV.js vendored (${(buf.length / 1e6).toFixed(1)} MB, ${opencv.integrity})`);
  } catch (e) {
    console.warn(`OpenCV.js not vendored (${e.message}); omr_scanner.html keeps loading it from docs.opencv.org`);
  }

  const files = new Set();
  for (const app of manifest.apps) { files.add(app.canonical); (app.aliases || []).forEach(a => files.add(a)); }

  for (const f of files) {
    let html = readFileSync(join(root, f), 'utf8');
    const hadBabel = /<script\s+type="text\/babel"/i.test(html);

    // 1. Compile JSX blocks
    html = html.replace(/<script\s+type="text\/babel"([^>]*)>([\s\S]*?)<\/script>/gi, (_, attrs, code) => {
      const out = Babel.transform(code, { presets: [['react', { runtime: 'classic' }]], sourceType: 'script', compact: false }).code;
      if (/<\/script/i.test(out)) throw new Error(`${f}: compiled code contains </script>`);
      return `<script${attrs}>\n${out}\n</script>`;
    });
    // Pending-validation questionnaire items stay hidden unless explicitly enabled for this build
    // (only after the UREC amendment and CVI validation are approved): DTAM_ENABLE_PENDING_ITEMS=1 npm run build
    if (process.env.DTAM_ENABLE_PENDING_ITEMS === '1') {
      html = html.replace(/const ENABLE_PENDING_ITEMS = false;/g, 'const ENABLE_PENDING_ITEMS = true;');
    }
    // Drop the in-browser compiler
    html = html.replace(new RegExp(`\\s*<script src="${esc(BABEL_URL)}"[^>]*></script>`, 'g'), '');

    // 2. Self-host vendor scripts
    for (const [url, v] of Object.entries(vendored)) {
      html = html.replace(new RegExp(`src="${esc(url)}"(\\s+integrity="([^"]+)")?`, 'g'), (m, _a, expected) => {
        if (expected && expected !== v.integrity)
          throw new Error(`${f}: ${url} integrity mismatch (source ${expected}, npm ${v.integrity})`);
        return `src="${v.path}" integrity="${v.integrity}"`;
      });
    }
    // 3. OpenCV
    if (opencv && html.includes(OPENCV_URL)) {
      html = html.replace(`src="${OPENCV_URL}"`, `src="${opencv.path}" integrity="${opencv.integrity}" crossorigin="anonymous"`);
    }

    // CSP: no CDN for self-hosted libraries; no 'unsafe-eval' once JSX is pre-compiled
    html = html.replace(/(<meta http-equiv="Content-Security-Policy" content=")([^"]*)(")/i, (_, a, csp, b) => {
      let c = csp.replace(/\s*https:\/\/cdn\.jsdelivr\.net/g, '');
      const needsWasmEval = html.includes(OPENCV_URL) || html.includes('opencv-4.8.0.js');
      if (hadBabel && !needsWasmEval) c = c.replace(/\s*'unsafe-eval'/g, '');
      if (opencv && html.includes(opencv.path)) c = c.replace(/\s*https:\/\/docs\.opencv\.org/g, '');
      return a + c + b;
    });

    if (/text\/babel/.test(html) || html.includes(BABEL_URL)) throw new Error(`${f}: Babel still referenced`);
    mkdirSync(dirname(join(dist, f)), { recursive: true });
    writeFileSync(join(dist, f), html);
    console.log(`built ${f}${hadBabel ? ' (JSX pre-compiled)' : ''}`);
  }
  copyFileSync(join(root, 'dtam_manifest.json'), join(dist, 'dtam_manifest.json'));
  writeFileSync(join(dist, 'BUILD_INFO.txt'),
    `DTAM-MY deployment build\nbuilt: ${new Date().toISOString()}\nsource commit: ${process.env.GIT_COMMIT || 'see git log'}\n` +
    `opencv: ${opencv ? 'self-hosted ' + opencv.integrity : 'docs.opencv.org (CDN)'}\n` +
    `pending-validation items: ${process.env.DTAM_ENABLE_PENDING_ITEMS === '1' ? 'ENABLED' : 'hidden'}\n`);
  console.log(`\nDone: ${dist}`);
}

main().catch(e => { console.error(e); process.exit(1); });
