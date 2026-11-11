/**
 * CopilotApi token + empty-body error regressions.
 * Run: node tests/js/api_client.test.mjs
 */
import assert from "node:assert/strict";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const apiUrl = pathToFileURL(
  path.resolve(__dirname, "../../finance_ops/web/copilot/js/api.js"),
).href;

const { CopilotApi, normalizeApiToken } = await import(apiUrl);

assert.equal(normalizeApiToken(null), null);
assert.equal(normalizeApiToken(undefined), null);
assert.equal(normalizeApiToken(""), null);
assert.equal(normalizeApiToken("   "), null);
assert.equal(normalizeApiToken("tok"), "tok");
assert.equal(normalizeApiToken("  tok  "), "tok");

const apiBlank = new CopilotApi({ token: "  " });
assert.equal(apiBlank.token, null);

let sawAuth = false;
const apiEmptyBody = new CopilotApi({
  fetchImpl: async () => {
    return {
      ok: false,
      status: 500,
      statusText: "",
      text: async () => "",
    };
  },
});
try {
  await apiEmptyBody.request("/v1/copilot/queue");
  assert.fail("expected throw");
} catch (err) {
  assert.equal(err.message, "HTTP 500");
  assert.equal(err.status, 500);
}

const apiWithToken = new CopilotApi({
  token: "secret",
  fetchImpl: async (_url, opts) => {
    sawAuth = opts.headers.get("Authorization") === "Bearer secret";
    return {
      ok: true,
      status: 200,
      statusText: "OK",
      text: async () => JSON.stringify({ status: "success" }),
    };
  },
});
await apiWithToken.request("/v1/copilot/status");
assert.equal(sawAuth, true);

console.log("api_client.test.mjs: ok");
