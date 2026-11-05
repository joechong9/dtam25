import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { setup, open } from './lib.mjs';

const zbiCard = () => [...document.querySelectorAll('div')].filter(d => d.textContent.startsWith('ZBI') && d.textContent.includes('Total')).pop()?.textContent;

test('OMR scanner: synthetic ZBI sheet, perspective warp, manual fix, safe CSV, no OpenCV leak', async () => {
  const env = await setup('file');
  try {
    const { page, errors } = await open(env, null);
    // Stretch the scanner's 400 ms readiness poll so the upload below always lands while the UI still says
    // "Loading…": correction must depend on OpenCV being ready, not on the polled badge state.
    await page.addInitScript(() => {
      const si = window.setInterval;
      window.setInterval = (f, ms, ...a) => si(f, ms === 400 ? 5000 : ms, ...a);
    });
    await page.goto(env.base + 'omr_scanner.html#CAREGIVER');
    await page.waitForFunction(() => window.cvReady === true, null, { timeout: 90000 });
    assert.equal(await page.$eval('select', s => s.value), 'CAREGIVER');
    const png = await page.evaluate(() => {
      const items = getAllItems('CAREGIVER').filter(i => i.page === 3);
      const K = 8, W = 297 * K, H = 210 * K, PAD = 120;
      const c = document.createElement('canvas'); c.width = W + 2 * PAD; c.height = H + 2 * PAD;
      const x = c.getContext('2d'); x.fillStyle = '#333'; x.fillRect(0, 0, c.width, c.height);
      x.fillStyle = '#fff'; x.fillRect(PAD, PAD, W, H); x.fillStyle = '#000';
      items.forEach(it => { x.beginPath(); x.arc(PAD + it.bubble_xs[0] * K, PAD + it.y_mm * K, 2.4 * K, 0, 7); x.fill(); });   // every item marked "0"
      return c.toDataURL('image/png').split(',')[1];
    });
    const img = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'dtam-')), 'zbi.png');
    fs.writeFileSync(img, Buffer.from(png, 'base64'));
    await page.fill('input[placeholder="e.g. CG-001"]', '=CG,001');
    await (await page.$$('input[type=file]'))[2].setInputFiles(img);
    await page.waitForTimeout(2000);
    assert.match(await page.textContent('text=/source/'), /2339×1654px source/, 'sheet perspective-corrected to A4 @200dpi');
    await page.click('text=/Process \\(/'); await page.waitForTimeout(1500);
    assert.match(await page.evaluate(zbiCard), /Total0\/88/, 'all-"0" ZBI sheet scores 0');
    await (await page.$('tr:has(td:text-is("ZBI_1")) select')).selectOption('4'); await page.waitForTimeout(200);
    assert.match(await page.evaluate(zbiCard), /Total4\/88/, 'manual correction re-scores');
    const dl = page.waitForEvent('download'); await page.click('text=⬇ CSV');
    const csv = fs.readFileSync(await (await dl).path(), 'utf8');
    assert.ok(csv.startsWith('\uFEFF'));
    assert.match(csv.split('\n')[1], /^\uFEFF?"'=CG,001","CAREGIVER","paper"/, 'participant ID quoted and formula-guarded; capture mode column');
    const [before, after] = await page.evaluate(() => {
      const c = document.createElement('canvas'); c.width = 1200; c.height = 900;
      const x = c.getContext('2d'); x.fillStyle = '#333'; x.fillRect(0, 0, 1200, 900); x.fillStyle = '#fff'; x.fillRect(100, 80, 1000, 700);
      for (let i = 0; i < 3; i++) detectAndWarp(c);
      const b = cv.HEAPU8.length; for (let i = 0; i < 40; i++) detectAndWarp(c); return [b, cv.HEAPU8.length];
    });
    assert.equal(after, before, 'WASM heap stable across 40 warps');
    assert.deepEqual(errors.filter(e => !/octet-stream/.test(e)), []);
  } finally { await env.close(); }
});

// WHOQOL-BREF: each domain scored with at most one missing item (mean of answered items).
const DOMAINS = { Physical: [3, 4, 10, 15, 16, 17, 18], Psychological: [5, 6, 7, 11, 19, 26], Social: [20, 21, 22], Environment: [8, 9, 12, 13, 14, 23, 24, 25] };
const REV = [3, 4, 26];
const RAW = Object.fromEntries(Array.from({ length: 26 }, (_, i) => [i + 1, ((i + 1) % 5) + 1]));
const expected = (domain, drop) => {
  const items = DOMAINS[domain].filter(i => !drop.includes(i));
  if (items.length < DOMAINS[domain].length - 1) return null;
  return (items.reduce((a, i) => a + (REV.includes(i) ? 6 - RAW[i] : RAW[i]), 0) / items.length - 1) * 25;
};

test('WHOQOL-BREF: questionnaire and OMR scanner apply the same missing-item rule', async () => {
  const env = await setup('file');
  try {
    const q = await open(env, 'telerehab_questionnaire_app_v2.html'); await q.page.waitForSelector('.btn-hero');
    const o = await open(env, 'omr_scanner.html'); await o.page.waitForTimeout(1500);
    const omrKey = { Physical: 'physical', Psychological: 'psychological', Social: 'social', Environment: 'environmental' };
    for (const [domain, items] of Object.entries(DOMAINS)) {
      for (const drop of [[], [items[0]], [items[0], items[1]]]) {
        const exp = expected(domain, drop);
        const answers = {}; for (let i = 1; i <= 26; i++) if (!drop.includes(i)) answers['wq' + i] = String(RAW[i]);
        const qv = await q.page.evaluate(([a, d]) => scoreSurvey('elderly', a)[`WHOQOL_${d}`]?.value ?? null, [answers, domain]);
        const ov = await o.page.evaluate(([r, dropCodes, k]) => {
          const res = getAllItems('ELDERLY').filter(i => i.code.startsWith('WHOQ_') && !dropCodes.includes(i.code))
            .map(i => ({ ...i, selectedValue: String(r[i.code.slice(5)]) }));
          const w = computeScores(res).whoqol; return w[k] == null ? null : Number(w[k]);
        }, [RAW, drop.map(i => 'WHOQ_' + i), omrKey[domain]]);
        const label = `${domain}, ${drop.length} missing`;
        if (exp === null) { assert.equal(qv, null, label); assert.equal(ov, null, label); }
        else { assert.equal(qv, Math.round(exp), label); assert.ok(Math.abs(ov - exp) < 0.051, `${label}: ${ov} vs ${exp}`); }
      }
    }
    // a blank (cleared) answer counts as missing, not NaN
    const blank = await q.page.evaluate(() => { const a = {}; for (let i = 1; i <= 26; i++) a['wq' + i] = '4'; a.wq20 = '5'; a.wq21 = ''; a.wq22 = '3'; return scoreSurvey('elderly', a).WHOQOL_Social.value; });
    assert.equal(blank, 75);
    assert.deepEqual([...q.errors, ...o.errors], []);
  } finally { await env.close(); }
});
