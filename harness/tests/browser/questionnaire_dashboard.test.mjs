import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { setup, open } from './lib.mjs';

async function completeCaregiver(page, langBtn) {
  await page.waitForSelector('.btn-hero');
  await page.click(`.lang-btn:has-text("${langBtn}")`);
  await page.click('.btn-hero');
  await page.click('.group-card >> nth=1');   // caregiver
  await page.click('.btn-primary.btn-lg');
  for (const cb of await page.$$('input[type=checkbox]')) await cb.check();
  await page.click('.btn-primary:not([disabled]) >> nth=-1');
  for (let guard = 0; guard < 12 && await page.$('.nav-btns'); guard++) {
    for (const s of await page.$$('select.select-input')) {
      const opts = await s.$$eval('option', o => o.map(x => x.value).filter(Boolean)); await s.selectOption(opts[0]);
    }
    const names = await page.$$eval('.likert-wrap input[type=radio]', r => [...new Set(r.map(x => x.name))]);
    for (const n of names) await page.click(`label[for="${n}_0"]`);
    await page.dblclick('.nav-btns .btn-primary');   // a double-click must not submit twice
    await page.waitForTimeout(150);
  }
}

test('questionnaire: records survey language, ZBI 0, single submit', async () => {
  const env = await setup('file');
  try {
    const { page, errors } = await open(env, 'telerehab_questionnaire_app_v2.html');
    await completeCaregiver(page, 'தமிழ்');
    const recs = await page.evaluate(() => JSON.parse(localStorage.getItem('dtam_my_responses')));
    assert.equal(recs.length, 1);
    assert.equal(recs[0].lang, 'ta');
    assert.equal(recs[0].scores.ZBI.value, 0);
    assert.deepEqual(errors, []);
  } finally { await env.close(); }
});

test('questionnaire: a failed local save shows a warning and offers a download', async () => {
  const env = await setup('file');
  try {
    const { page, errors } = await open(env, null);
    await page.addInitScript(() => {
      const orig = Storage.prototype.setItem;
      Storage.prototype.setItem = function (k, v) { if (k === 'dtam_my_responses') throw new DOMException('quota', 'QuotaExceededError'); return orig.call(this, k, v); };
    });
    await page.goto(env.base + 'telerehab_questionnaire_app_v2.html');
    await completeCaregiver(page, 'EN');
    assert.ok(await page.isVisible('[role=alert]'), 'save-failure warning shown instead of success');
    const dl = page.waitForEvent('download'); await page.click('[role=alert] button');
    const rec = JSON.parse(fs.readFileSync(await (await dl).path(), 'utf8'));
    assert.equal(rec.group, 'caregiver'); assert.ok(Object.keys(rec.answers).length > 40);
    assert.deepEqual(errors, []);
  } finally { await env.close(); }
});

test('dashboard: ZBI interpretation, all states, survey language, lazy embed, safe CSV, works without Chart.js', async () => {
  for (const block of [null, /chart\.umd/]) {
    const env = await setup('http', { block });
    try {
      const { page, errors } = await open(env, 'telerehab_dashboard_v2.html');
      const requests = []; page.on('request', r => requests.push(r.url()));
      await page.evaluate(() => {
        const now = new Date(), yearAgo = new Date(now); yearAgo.setFullYear(now.getFullYear() - 1);
        localStorage.setItem('dtam_my_responses', JSON.stringify([
          { id: 'X-<img src=x onerror="window.__xss=1">', timestamp: now.toISOString(), group: 'caregiver', lang: 'ta', meta: { lang: 'en-US' }, answers: { d4: 'Sabah', note: '=1+1' }, scores: { ZBI: { value: 30 } } },
          { id: 'Y-1', timestamp: yearAgo.toISOString(), group: 'allied', meta: { lang: 'en-US' }, answers: { d4: 'Sarawak' }, scores: { SUS: { value: 72.5 }, TAM_PU: { value: 3.7 } } },
        ]));
      });
      await page.reload(); await page.waitForTimeout(800);
      await page.click('.tab-btn:has-text("Scores")'); await page.waitForTimeout(300);
      const row = await page.$eval('#score-table-body', t => [...t.rows].find(r => r.cells[0].textContent === 'ZBI').innerText);
      assert.match(row, /Mild-Moderate/, 'ZBI 30 is Mild-Moderate, not "High"');
      if (!block) {
        assert.equal(await page.evaluate(() => charts['chart-timeline'].data.datasets[0].data.reduce((a, b) => a + b, 0)), 1, 'year-old record outside 30-day timeline');
        assert.deepEqual(await page.evaluate(() => charts['chart-lang'].data.labels), ['Tamil', 'English']);
        await page.click('.tab-btn:has-text("Demographics")'); await page.waitForTimeout(300);
        assert.deepEqual(await page.evaluate(() => { const c = charts['chart-state']; return c.data.labels.filter((l, i) => c.data.datasets[0].data[i] > 0); }), ['Sabah', 'Sarawak']);
        const dl = page.waitForEvent('download'); await page.evaluate(() => exportCSV());
        const csv = fs.readFileSync(await (await dl).path(), 'utf8');
        assert.ok(csv.startsWith('﻿')); assert.ok(csv.includes(`"'=1+1"`), 'formula guarded in export');
      }
      await page.click('.tab-btn:has-text("Responses")'); await page.waitForTimeout(200);
      assert.equal(await page.evaluate(() => !!window.__xss), false);
      assert.ok(!requests.some(u => /omr_scanner\.html/.test(u)), 'embedded scanner not loaded until opened');
      await page.click('.tab-btn:has-text("OMR Scanner")'); await page.click('button:has-text("Embed Here")'); await page.waitForTimeout(3000);
      assert.ok(await page.evaluate(() => !!document.querySelector('#omr-embed iframe').contentDocument.querySelector('select')), 'embedded scanner renders');
      // With Chart.js deliberately blocked, the browser logs the failed request itself; nothing else may error.
      assert.deepEqual(errors.filter(e => !(block && /Failed to load resource/.test(e))), []);
    } finally { await env.close(); }
  }
});
