// Google account link / restore:  node supabase/functions/scores/tests/google_link_test.ts
import http from "node:http";
import assert from "node:assert/strict";

const pair = await crypto.subtle.generateKey({ name: "RSASSA-PKCS1-v1_5", modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]),
                                              hash: "SHA-256" }, true, ["sign", "verify"]);
const other = await crypto.subtle.generateKey({ name: "RSASSA-PKCS1-v1_5", modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]),
                                               hash: "SHA-256" }, true, ["sign", "verify"]);
const jwk: any = await crypto.subtle.exportKey("jwk", pair.publicKey);
const srv = http.createServer((_q, r) => { r.setHeader("content-type", "application/json");
  r.end(JSON.stringify({ keys: [{ kty: "RSA", kid: "k1", n: jwk.n, e: jwk.e, alg: "RS256", use: "sig" }] })); });
await new Promise<void>((res) => srv.listen(8813, res));
process.env.GOOGLE_CERTS_URL = "http://127.0.0.1:8813/certs";
process.env.GOOGLE_WEB_CLIENT_ID = "web-123.apps.googleusercontent.com";

const { handle, sha256Hex, signGoogleLink } = await import("../handler.ts");
const { MemStore } = await import("./mem.ts");

const b64u = (b: Uint8Array | string) => Buffer.from(typeof b === "string" ? b : Buffer.from(b)).toString("base64url");
async function token(claims: any, key = pair.privateKey, kid = "k1") {
  const head = b64u(JSON.stringify({ alg: "RS256", kid, typ: "JWT" }));
  const body = b64u(JSON.stringify(claims));
  const sig = new Uint8Array(await crypto.subtle.sign("RSASSA-PKCS1-v1_5", key, new TextEncoder().encode(`${head}.${body}`)));
  return `${head}.${body}.${b64u(sig)}`;
}
const now = Date.now(), ts = Math.floor(now / 1000);
const good = (sub: string, extra: any = {}) => token({ iss: "https://accounts.google.com", aud: "web-123.apps.googleusercontent.com",
  sub, email: "pilot.tester@gmail.com", email_verified: true, iat: ts - 10, exp: ts + 3600, ...extra });

const store = new MemStore();
const post = (route: string, body: any) => handle(store as any, "POST", route, new URLSearchParams(), JSON.stringify(body), "5.5.5." + Math.random(), now);
const pid = "e".repeat(32), sec = "f".repeat(48), pid2 = "1".repeat(32), sec2 = "2".repeat(48);
await post("/api/register", { player_id: pid, secret: sec, name: "LINKER", country: "TR" });
await post("/api/register", { player_id: pid2, secret: sec2, name: "OTHER", country: "DE" });
const link = async (p: string, s: string, tok: string) =>
  post("/api/account/google/link", { player_id: p, ts, id_token: tok, sig: await signGoogleLink(s, p, ts, await sha256Hex(tok)) });

let t = await good("g-111");
let r = await link(pid, sec, t);
assert.equal(r.status, 200, JSON.stringify(r.body));
assert.equal(r.body.email, "pi*********r@gmail.com");
r = await link(pid, "0".repeat(48), t);
assert.equal(r.status, 403, "link is signed by the pilot");
r = await link(pid2, sec2, t);
assert.equal(r.status, 409, "one Google account = one pilot");
r = await link(pid, sec, await good("g-111", { aud: "someone-else" }));
assert.equal(r.status, 401, "token for another app");
r = await link(pid, sec, await good("g-111", { exp: ts - 3600 }));
assert.equal(r.status, 401, "expired");
r = await link(pid, sec, await good("g-111", {}).then(() => token({ iss: "https://accounts.google.com", aud: "web-123.apps.googleusercontent.com",
  sub: "g-111", iat: ts, exp: ts + 60 }, other.privateKey)));
assert.equal(r.status, 401, "not signed by Google");

r = await post("/api/account/google/restore", { id_token: await good("g-111") });
assert.equal(r.status, 200);
assert.equal(r.body.player_id, pid);
assert.equal(r.body.secret, sec);
r = await post("/api/account/google/restore", { id_token: await good("g-999") });
assert.equal(r.status, 404, "no pilot linked to that Google account");
srv.close();
console.log("ALL GOOGLE LINK TESTS PASSED");
