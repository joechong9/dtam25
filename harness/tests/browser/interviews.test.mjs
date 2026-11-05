import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { setup, open, FAKE_SPEECH } from './lib.mjs';

test('Part C: a recording flushes into its own question, notes survive re-render, draft resumes, admin index written', async () => {
  const env = await setup('file');
  try {
    const { page, errors } = await open(env, null);
    await page.addInitScript(FAKE_SPEECH);
    await page.goto(env.base + 'partc_interview_v2.html');
    await page.fill('#f_rid', 'R"01'); await page.fill('#f_pid', 'CG-<b>7');
    await page.selectOption('#f_group', 'policymaker');
    await page.click('#btn_setup_next'); await page.check('#cb_consent'); await page.click('#btn_consent_next');
    const q1 = await page.evaluate(() => currentQuestion().code);
    await page.click('#btn_rec'); await page.waitForTimeout(50);
    await page.evaluate(() => window.__sr.emit('hello world'));
    await page.waitForTimeout(1100);
    await page.click('#btn_save');                                   // Save & Next while still recording
    await page.evaluate(() => window.__sr.emit('late words'));       // arrives during the 800 ms flush
    await page.waitForTimeout(1000);
    const r1 = await page.evaluate(code => getR(code), q1);
    assert.equal(r1.transcript, 'hello world late words');
    assert.ok(r1.recSecs >= 1);
    assert.equal(await page.inputValue('#ta_transcript'), '', 'next question untouched');
    await page.fill('#ta_notes', 'pain <severe & "sharp" </textarea>');
    await page.click('#btn_prev'); await page.click('#btn_save');
    assert.equal(await page.inputValue('#ta_notes'), 'pain <severe & "sharp" </textarea>');
    await page.reload(); await page.waitForTimeout(300);              // dialog (resume) is accepted
    assert.equal(await page.evaluate(code => S.responses[code].transcript, q1), 'hello world late words', 'draft resumed');
    for (let i = 0; i < 80 && await page.$('#btn_skip'); i++) await page.click('#btn_skip');
    const idx = await page.evaluate(() => JSON.parse(localStorage.getItem('dtam_my_interviews')));
    assert.equal(idx.length, 1); assert.equal(idx[0].group, 'policy');
    assert.ok(!JSON.stringify(idx).includes('hello'), 'admin index holds no transcripts');
    assert.deepEqual(errors, []);
  } finally { await env.close(); }
});

test('verbal interview: live transcript saved, score always chosen by the interviewer, no duplicates', async () => {
  const env = await setup('file');
  try {
    const { page, errors } = await open(env, null);
    await page.addInitScript(FAKE_SPEECH);
    await page.goto(env.base + 'verbal_interview_ui_v2.html');
    await page.fill('input[placeholder="e.g. R001"]', 'R1'); await page.fill('input[placeholder="e.g. ELD-001"]', 'E1');
    await page.click('text=Proceed to Consent');
    const consent = await page.textContent('.consent-box');
    assert.match(consent, /does not save an audio file/); assert.match(consent, /approval pending/);
    await page.check('input[type=checkbox]'); await page.click('text=Begin Interview');
    const rec = page.locator('.record-btn');
    const answer = async (spoken, score) => {
      await rec.click(); await page.waitForTimeout(100);
      await page.evaluate(t => window.__sr.emit(t), spoken);
      await rec.click(); await page.waitForTimeout(500);
      assert.ok(await page.isDisabled('text=Confirm & Next →'), 'no score is pre-selected');
      await page.click(`.likert-row button >> nth=${score - 1}`);
      await page.click('text=Confirm & Next →');
    };
    await answer('very good', 2);
    await page.click('text=← Back');
    await answer('actually good', 4);                                 // re-answer item 1: replaces, not duplicates
    for (let i = 0; i < 20 && !(await page.$('text=Session Complete')); i++) await answer('ok', 3);
    const dl = page.waitForEvent('download'); await page.click('text=Export JSON');
    const j = JSON.parse(fs.readFileSync(await (await dl).path(), 'utf8'));
    const codes = j.items.map(e => e.code);
    assert.equal(codes.length, new Set(codes).size, 'no duplicate items');
    const first = j.items.find(e => e.transcript === 'actually good');
    assert.ok(first && first.confirmedScore === 4 && first.stt === 'browser');
    assert.ok(j.items.every(e => !('autoScore' in e)), 'nothing is machine-scored');
    assert.deepEqual(errors, []);
  } finally { await env.close(); }
});
