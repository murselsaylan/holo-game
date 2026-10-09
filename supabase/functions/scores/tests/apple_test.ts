import { handle, setAppleVerifier, signWallet, sha256Hex } from "../handler.ts";
import { appleVerifier } from "../apple.ts";
import { MemStore } from "./mem.ts";
import assert from "node:assert/strict";

const store = new MemStore();
const A = "a".repeat(32), SA = "b".repeat(48);
const now = Date.now();
const post = async (body: any) => handle(store as any, "POST", "/api/wallet", new URLSearchParams(), JSON.stringify(body), "9.9.9." + Math.random(), now);
async function w(op: string, extra: any) {
  const ts = Math.floor(now / 1000);
  const key = op === "sync" ? String(extra.local ?? 0) : extra.product;
  return post({ player_id: A, ts, op, ...extra, sig: await signWallet(SA, A, ts, op, key, extra.ref ?? "") });
}
const buy = async (product: string, token: string, receipt = "") => w("purchase", { product, token, ref: await sha256Hex(token), receipt });

await handle(store as any, "POST", "/api/register", new URLSearchParams(), JSON.stringify({ player_id: A, secret: SA, name: "X", country: "TR" }), "1.1.1.1", now);
await w("sync", { local: 0 });

// ---- routing: "ios:" tokens go to the App Store verifier, with the receipt
let seen: any[] = [];
setAppleVerifier(async (product, tid, receipt) => {
  seen.push([product, tid, receipt]);
  return tid === "2000000111" ? { state: "purchased", orderId: "APPLE." + tid, account: "", consumed: false, test: true }
    : { state: "cancelled", orderId: "", account: "", consumed: false, test: false };
});
let r = await buy("pack_350", "ios:2000000111", "UkVDRUlQVA==");
assert.equal(r.status, 200); assert.equal(r.body.balance, 350);
assert.deepEqual(seen[0], ["pack_350", "2000000111", "UkVDRUlQVA=="]);
r = await buy("pack_350", "ios:2000000111"); assert.equal(r.body.dup, true); assert.equal(r.body.balance, 350);
r = await buy("pack_100", "ios:999"); assert.equal(r.status, 410);
setAppleVerifier(appleVerifier);

// ---- the verifier itself against a fake Apple
const env = (globalThis as any).process.env;
env.APPLE_API_BASE = "https://apple.test";
const realFetch = globalThis.fetch;
const b64u = (o: any) => Buffer.from(JSON.stringify(o)).toString("base64url");
let calls: string[] = [];
let receiptReply: any = null;
(globalThis as any).fetch = async (url: string, init: any) => {
  calls.push(url);
  if (url.endsWith("/verifyReceipt")) return new Response(JSON.stringify(receiptReply), { status: 200 });
  const m = /transactions\/(\d+)$/.exec(url);
  assert.ok(init.headers.Authorization.startsWith("Bearer "));
  const jwt = init.headers.Authorization.slice(7).split(".");
  const head = JSON.parse(Buffer.from(jwt[0], "base64url").toString());
  assert.equal(head.alg, "ES256"); assert.equal(head.kid, "KEY123");
  assert.equal(Buffer.from(jwt[2], "base64url").length, 64);       // raw r||s
  if (!m || m[1] === "404") return new Response("{}", { status: 404 });
  const t: any = { transactionId: m[1], bundleId: "com.hologame.holo", productId: "pack_1000", environment: "Sandbox" };
  if (m[1] === "7") t.revocationDate = 1;
  return new Response(JSON.stringify({ signedTransactionInfo: `${b64u({ alg: "ES256" })}.${b64u(t)}.sig` }), { status: 200 });
};

// no key yet: the receipt is checked
receiptReply = { status: 0, environment: "Sandbox", receipt: { bundle_id: "com.hologame.holo", in_app: [
  { transaction_id: "55", product_id: "pack_1000" }, { transaction_id: "56", product_id: "skin_big_bang", cancellation_date: "x" }] } };
assert.equal((await appleVerifier("pack_1000", "55", "R"))!.state, "purchased");
assert.equal((await appleVerifier("pack_2500", "55", "R"))!.state, "cancelled");     // other product
assert.equal((await appleVerifier("skin_big_bang", "56", "R"))!.state, "cancelled"); // refunded
assert.equal((await appleVerifier("pack_1000", "57", "R"))!.state, "cancelled");     // not in the receipt
assert.equal(await appleVerifier("pack_1000", "55", ""), null);                        // nothing to check with
receiptReply.receipt.bundle_id = "com.other.app";
assert.equal((await appleVerifier("pack_1000", "55", "R"))!.state, "cancelled");
assert.equal((await appleVerifier("pack_1000", "abc", "R"))!.state, "cancelled");    // not a transaction id

// with the In-App Purchase key: the App Store Server API
const kp = await crypto.subtle.generateKey({ name: "ECDSA", namedCurve: "P-256" }, true, ["sign", "verify"]);
const pk = Buffer.from(await crypto.subtle.exportKey("pkcs8", kp.privateKey)).toString("base64");
env.APPLE_IAP_KEY = `-----BEGIN PRIVATE KEY-----\n${pk.match(/.{1,64}/g)!.join("\n")}\n-----END PRIVATE KEY-----`;
env.APPLE_IAP_KEY_ID = "KEY123"; env.APPLE_ISSUER_ID = "issuer";
calls = [];
let p = await appleVerifier("pack_1000", "123", "");
assert.equal(p!.state, "purchased"); assert.equal(p!.orderId, "APPLE.123"); assert.equal(p!.test, true);
assert.ok(calls[0].endsWith("/inApps/v1/transactions/123"));
assert.equal((await appleVerifier("pack_350", "123", ""))!.state, "cancelled");      // other product
assert.equal((await appleVerifier("pack_1000", "7", ""))!.state, "cancelled");       // refunded
assert.equal((await appleVerifier("pack_1000", "404", ""))!.state, "cancelled");     // unknown
(globalThis as any).fetch = realFetch;
console.log("ALL APPLE TESTS PASSED");
