import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { setup, open } from './lib.mjs';

const PASS = 'password123';

async function firstRun(page, name = 'PI', email = 'pi@x.my') {
  await page.fill('#reg-name', name); await page.fill('#reg-email', email);
  await page.fill('#reg-pass', PASS); await page.fill('#reg-pass2', PASS);
  await page.click('#reg-btn'); await page.waitForTimeout(1500);
}
async function login(page, user, pass = PASS) {
  await page.fill('#login-user', user); await page.fill('#login-pass', pass);
  await page.click('#login-btn'); await page.waitForTimeout(900);
}
async function register(page, name, email, code) {
  await page.evaluate(() => showRegister());
  await page.fill('#reg-name', name); await page.fill('#reg-email', email);
  await page.fill('#reg-pass', PASS); await page.fill('#reg-pass2', PASS);
  await page.fill('#reg-code', code);
  await page.click('#reg-btn'); await page.waitForTimeout(1500);
  return page.$eval('#reg-success', e => e.style.display !== 'none');
}
const logout = async page => { await page.evaluate(() => sessionStorage.removeItem(SESSION_KEY)); await page.reload(); await page.waitForTimeout(300); };

test('auth: PBKDF2 accounts, legacy upgrade, lockout survives refresh', async () => {
  const env = await setup('http');
  try {
    const { page, errors } = await open(env, 'admin_portal_v2.html');
    await firstRun(page);
    const acc = await page.evaluate(() => JSON.parse(localStorage.getItem('dtam_admin_users_v2'))[0]);
    assert.equal(acc.kdf, 'pbkdf2-sha256-210000'); assert.ok(acc.salt);
    await page.evaluate(async () => {
      const arr = JSON.parse(localStorage.getItem('dtam_admin_users_v2'));
      arr.push({ username: 'old@x.my', passwordHash: await hashPassword('legacypass1'), display: 'Old', builtin: false });
      localStorage.setItem('dtam_admin_users_v2', JSON.stringify(arr));
    });
    await page.reload();
    for (let i = 0; i < 5; i++) await login(page, 'pi@x.my', 'wrong');
    await page.reload(); await login(page, 'pi@x.my');
    assert.match(await page.textContent('#login-error'), /Try again in/, 'lockout must survive a refresh');
    await page.evaluate(() => sessionStorage.setItem('dtam_login_lock_until', String(Date.now() - 1)));
    await login(page, 'old@x.my', 'legacypass1');
    assert.ok(await page.isVisible('#sidebar'));
    const up = await page.evaluate(() => JSON.parse(localStorage.getItem('dtam_admin_users_v2')).find(a => a.username === 'old@x.my'));
    assert.equal(up.kdf, 'pbkdf2-sha256-210000', 'legacy SHA-256 record upgraded on login');
    assert.deepEqual(errors, []);
  } finally { await env.close(); }
});

test('OMR import is escaped; CSV keeps 0, has BOM and guards formulas; chat bubbles are text', async () => {
  const env = await setup('http');
  try {
    const { page, errors } = await open(env, 'admin_portal_v2.html');
    await firstRun(page); await login(page, 'pi@x.my');
    const tmp = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'dtam-')), 'omr.json');
    fs.writeFileSync(tmp, JSON.stringify([{ participant_id: '<img src=x onerror="window.__xss=1">', sheet: 'CAREGIVER',
      timestamp: '2026-01-01T00:00:00Z', results: [{ code: 'ZBI_1', label: '=HYPERLINK("x")', selectedValue: 0, maxFill: 0.6 },
        { code: 'ZBI_2', label: 'neg', selectedValue: -1, maxFill: 0.5 }], scores: { zbi: { total: 0 } } }]));
    await page.setInputFiles('input[type=file][onchange*="importOmrJson"]', tmp); await page.waitForTimeout(400);
    assert.equal(await page.evaluate(() => !!window.__xss), false, 'imported participant_id must not execute');
    await page.evaluate(() => closeModal());
    const dl = page.waitForEvent('download'); await page.evaluate(() => exportOmrCSV());
    const csv = fs.readFileSync(await (await dl).path(), 'utf8');
    assert.ok(csv.startsWith('﻿'), 'CSV starts with a UTF-8 BOM');
    const rows = csv.slice(1).split('\n');
    assert.match(rows[1], /"'=HYPERLINK\(""x""\)","0"/, 'formula text is guarded and 0 is kept');
    assert.match(rows[2], /"neg","-1"/, 'plain negative numbers are not altered');
    await page.evaluate(() => { _claudeKey = 'k'; toggleChat(); });
    await page.fill('#chat-input', '<b>hi</b>'); await page.press('#chat-input', 'Enter'); await page.press('#chat-input', 'Enter');
    await page.waitForTimeout(800);
    const bubbles = await page.$$eval('#chat-msgs .chat-msg', m => m.map(x => x.className.split(' ')[1] + ':' + x.textContent));
    assert.deepEqual(bubbles.slice(1), ['user:<b>hi</b>', 'model:REPLY-OK'], 'one request; reply replaces the typing bubble');
    assert.deepEqual(errors, []);
  } finally { await env.close(); }
});

test('registration tokens: single use, expiry, revocation, hashed storage', async () => {
  const env = await setup('http');
  try {
    const { page, errors } = await open(env, 'admin_portal_v2.html');
    await firstRun(page); await login(page, 'pi@x.my');
    await page.evaluate(() => showSection('settings', null));
    const issue = async (label) => {
      await page.fill('#tok-label', label); await page.click('text=+ Generate Token'); await page.waitForTimeout(400);
      const code = (await page.textContent('#modal-msg')).split('\n')[0];
      await page.click('#modal-btns >> text=Done');
      return code;
    };
    const good = await issue('Good'), revoked = await issue('Revoked'), expired = await issue('Expired');
    assert.match(good, /^[A-Z2-9]{4}-[A-Z2-9]{4}-[A-Z2-9]{4}$/);
    await page.click('#tokens-table tr:has-text("Revoked") button'); await page.click('#modal-btns >> text=Revoke');
    await page.evaluate(() => { const t = getRegTokens(); t.find(x => x.label === 'Expired').expiresAt = new Date(0).toISOString(); saveRegTokens(t); });
    const stored = await page.evaluate(() => localStorage.getItem('dtam_reg_tokens'));
    for (const c of [good, revoked, expired]) assert.ok(!stored.includes(c) && !stored.includes(c.replace(/-/g, '')), 'token text never stored');
    await logout(page);
    assert.equal(await register(page, 'X', 'x@x.my', 'ABCD-EFGH-JKLM'), false);
    assert.equal(await register(page, 'X', 'x@x.my', revoked), false);
    assert.equal(await register(page, 'X', 'x@x.my', expired), false);
    assert.equal(await register(page, 'New', 'new@x.my', ' ' + good.toLowerCase().replace(/-/g, ' ') + ' '), true);
    assert.equal(await register(page, 'Again', 'again@x.my', good), false, 'single use');
    await login(page, 'new@x.my');
    assert.ok(await page.isVisible('#sidebar'));
    assert.deepEqual(errors, []);
  } finally { await env.close(); }
});
