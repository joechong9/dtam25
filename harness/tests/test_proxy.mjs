// Tests for proxy/claude-proxy-worker.js with a mocked upstream.
// Run: node harness/tests/test_proxy.mjs
import assert from "node:assert/strict";
import worker from "../../proxy/claude-proxy-worker.js";

const ORIGIN = "https://joechong9.github.io";
const env = { ANTHROPIC_API_KEY: "sk-test", ALLOWED_ORIGINS: ORIGIN, PORTAL_TOKEN: "t0k" };
let lastUpstream = null;
globalThis.fetch = async (url, init) => {
  lastUpstream = { url, init, body: JSON.parse(init.body) };
  return new Response(JSON.stringify({ content: [{ type: "text", text: "ok" }] }), { status: 200 });
};

function req(body, { origin = ORIGIN, token = "t0k", method = "POST", path = "/v1/messages" } = {}) {
  const headers = { "content-type": "application/json", Origin: origin };
  if (token) headers["x-dtam-token"] = token;
  return new Request("https://proxy.example.workers.dev" + path, {
    method, headers, body: method === "POST" ? JSON.stringify(body) : undefined,
  });
}
const msg = { messages: [{ role: "user", content: "hi" }] };
let passed = 0;
async function t(name, fn) { await fn(); passed++; console.log("ok -", name); }

await t("rejects unknown origin", async () => {
  const r = await worker.fetch(req(msg, { origin: "https://evil.example" }), env);
  assert.equal(r.status, 403);
});
await t("rejects missing portal token", async () => {
  const r = await worker.fetch(req(msg, { token: null }), env);
  assert.equal(r.status, 401);
});
await t("answers CORS preflight", async () => {
  const r = await worker.fetch(req(null, { method: "OPTIONS" }), env);
  assert.equal(r.status, 204);
  assert.equal(r.headers.get("Access-Control-Allow-Origin"), ORIGIN);
});
await t("forwards with server-side key, strips fields, caps tokens", async () => {
  const r = await worker.fetch(req({ ...msg, model: "claude-haiku-5-5", max_tokens: 99999,
    tools: [{ name: "x" }], metadata: { a: 1 } }), env);
  assert.equal(r.status, 200);
  assert.equal(lastUpstream.init.headers["x-api-key"], "sk-test");
  assert.equal(lastUpstream.body.max_tokens, 4096);
  assert.equal(lastUpstream.body.model, "claude-haiku-5-5");
  assert.equal(lastUpstream.body.tools, undefined);
  assert.equal(lastUpstream.body.metadata, undefined);
});
await t("replaces non-allowlisted model with the default", async () => {
  await worker.fetch(req({ ...msg, model: "claude-fable-5-1" }), env);
  assert.equal(lastUpstream.body.model, "claude-haiku-5-5");
});
await t("rejects other paths", async () => {
  const r = await worker.fetch(req(msg, { path: "/v1/models" }), env);
  assert.equal(r.status, 404);
});
console.log(`${passed} proxy tests passed`);
