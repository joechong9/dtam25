import { test } from 'node:test';
import assert from 'node:assert/strict';
import { setup, open } from './lib.mjs';

test('landing chat: visitor text escaped, stale reply dropped on language switch, IME Enter ignored', async () => {
  const env = await setup('file');
  try {
    const { page, errors } = await open(env, 'index.html');
    await page.click('#chatFab'); await page.waitForTimeout(400);
    await page.fill('#chatInput', '<img src=x onerror="window.__xss=1"> what is dtam'); await page.press('#chatInput', 'Enter');
    await page.waitForTimeout(1200);
    assert.equal(await page.evaluate(() => !!window.__xss), false);
    await page.fill('#chatInput', 'how do I participate'); await page.press('#chatInput', 'Enter');
    await page.evaluate(() => setLang('bm')); await page.waitForTimeout(1300);
    assert.deepEqual(await page.$$eval('#chatMessages .msg', m => m.map(x => x.className)), ['msg bot'], 'only the new greeting');
    const before = await page.$$eval('.msg.user', m => m.length);
    await page.fill('#chatInput', 'ni hao');
    await page.dispatchEvent('#chatInput', 'keydown', { key: 'Enter', isComposing: true });
    assert.equal(await page.$$eval('.msg.user', m => m.length), before);
    assert.deepEqual(errors, []);
  } finally { await env.close(); }
});

test('ethics wording: approval pending and application not yet submitted, in all four languages', async () => {
  const env = await setup('file');
  try {
    const idx = await open(env, 'index.html');
    const chat = await idx.page.evaluate(() => ['en', 'bm', 'zh', 'ta'].map(l => {
      window._lang = l; const d = document.createElement('div'); d.innerHTML = findResponse('privacy').reply; return d.textContent;
    }));
    assert.match(chat[0], /awaiting submission/); assert.match(chat[1], /belum dikemukakan/);
    assert.match(chat[2], /尚未提交/); assert.match(chat[3], /இன்னும் சமர்ப்பிக்கப்படவில்லை/);
    const q = await open(env, 'telerehab_questionnaire_app_v2.html'); await q.page.waitForSelector('.btn-hero');
    const expectations = { EN: /approval .* is pending/, BM: /menunggu kelulusan/, '中文': /等待/, 'தமிழ்': /நிலுவையில்/ };
    for (const [btn, rx] of Object.entries(expectations)) {
      await q.page.click(`.lang-btn:text-is("${btn}")`);
      await q.page.click('.btn-hero'); await q.page.click('.group-card >> nth=0'); await q.page.click('.btn-primary.btn-lg');
      const sec8 = await q.page.evaluate(() => { const s = [...document.querySelectorAll('.consent-section')].find(x => x.textContent.startsWith('8')); return s.nextElementSibling.textContent; });
      const sec5 = await q.page.evaluate(() => { const s = [...document.querySelectorAll('.consent-section')].find(x => x.textContent.startsWith('5')); return s.nextElementSibling.textContent; });
      assert.match(sec8, rx, `consent §8 (${btn})`);
      assert.doesNotMatch(sec8, /submitted|dikemukakan kepada|已提交|சமர்ப்பிக்கப்பட்டுள்ளது/, `no submission claim (${btn})`);
      assert.match(sec5, /device|peranti|设备|சாதன/, `consent §5 mentions on-device storage (${btn})`);
      await q.page.goto(env.base + 'telerehab_questionnaire_app_v2.html'); await q.page.waitForSelector('.btn-hero');
    }
    assert.deepEqual([...idx.errors, ...q.errors], []);
  } finally { await env.close(); }
});

test('integration: questionnaire and Part C data appear in the admin portal and dashboard', async () => {
  const env = await setup('http');
  try {
    const q = await open(env, 'telerehab_questionnaire_app_v2.html'); await q.page.waitForSelector('.btn-hero');
    await q.page.evaluate(() => submitResponse('caregiver', { d4: 'Sarawak' }, { ZBI: { value: 12, max: 88 } }, 'zh'));
    const c = await open(env, 'partc_interview_v2.html');
    await c.page.fill('#f_rid', 'R7'); await c.page.fill('#f_pid', 'EL-3'); await c.page.selectOption('#f_group', 'elderly');
    await c.page.click('#btn_setup_next'); await c.page.check('#cb_consent'); await c.page.click('#btn_consent_next');
    for (let i = 0; i < 80 && await c.page.$('#btn_skip'); i++) await c.page.click('#btn_skip');
    const a = await open(env, 'admin_portal_v2.html');
    await a.page.fill('#reg-name', 'PI'); await a.page.fill('#reg-email', 'pi@x.my');
    await a.page.fill('#reg-pass', 'longpassword1'); await a.page.fill('#reg-pass2', 'longpassword1');
    await a.page.click('#reg-btn'); await a.page.waitForTimeout(2500);
    await a.page.fill('#login-user', 'pi@x.my'); await a.page.fill('#login-pass', 'longpassword1'); await a.page.click('#login-btn');
    await a.page.waitForTimeout(800);
    assert.match(await a.page.textContent('#participant-table'), /Caregiver[\s\S]*ZH/);
    assert.match(await a.page.textContent('#interview-table'), /Elderly Patient[\s\S]*R7/);
    const d = await open(env, 'telerehab_dashboard_v2.html'); await d.page.waitForTimeout(800);
    assert.deepEqual(await d.page.evaluate(() => charts['chart-lang'].data.labels), ['Chinese']);
    assert.deepEqual([...q.errors, ...c.errors, ...a.errors, ...d.errors], []);
  } finally { await env.close(); }
});
