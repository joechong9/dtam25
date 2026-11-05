import { test } from 'node:test';
import assert from 'node:assert/strict';
import { setup, open, CANONICAL_PAGES } from './lib.mjs';

for (const mode of ['file', 'http']) {
  test(`every canonical page renders without errors (${mode})`, async () => {
    const env = await setup(mode);
    try {
      for (const f of CANONICAL_PAGES) {
        const { page, errors } = await open(env, f);
        await page.waitForTimeout(1500);
        const text = await page.evaluate(() => document.body.innerText.trim().length);
        assert.ok(text > 100, `${f} rendered no content (${mode}) — a CSP or script error leaves React apps blank`);
        assert.deepEqual(errors.filter(e => !/opencv/i.test(e)), [], `${f} (${mode})`);
        await page.close();
      }
    } finally { await env.close(); }
  });

  test(`alias stubs redirect and keep query/hash (${mode})`, async () => {
    const env = await setup(mode);
    try {
      const { page } = await open(env, null);
      const cases = [
        ['index_v2.html', 'index.html', null],
        ['telerehab_dashboard.html', 'telerehab_dashboard_v2.html', null],
        ['omr_scanner_v2.html?sheet=ELDERLY', 'omr_scanner.html?sheet=ELDERLY', 'ELDERLY'],
        ['omr_scanner_v2.html#POLICY_MAKER', 'omr_scanner.html#POLICY_MAKER', 'POLICY_MAKER'],
      ];
      for (const [from, to, sheet] of cases) {
        await page.goto(env.base + from);
        await page.waitForTimeout(1500);
        assert.equal(page.url().split('/').pop(), to);
        if (sheet) assert.equal(await page.$eval('select', s => s.value), sheet, `sheet preselect after ${from}`);
      }
    } finally { await env.close(); }
  });
}
