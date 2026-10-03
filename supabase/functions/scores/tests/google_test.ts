// googleVerifier against a fake Google (OAuth token endpoint + Android Publisher API) with a real RSA service-account key.
import http from "node:http";
import { generateKeyPairSync, createVerify } from "node:crypto";
import assert from "node:assert/strict";

const { privateKey, publicKey } = generateKeyPairSync("rsa", { modulusLength: 2048 });
const pem = privateKey.export({ type: "pkcs8", format: "pem" }).toString();
let tokenCalls = 0, apiCalls = 0;
const srv = http.createServer(async (req, res) => {
  let body = ""; for await (const c of req) body += c;
  if (req.url === "/token") {
    tokenCalls++;
    const jwt = new URLSearchParams(body).get("assertion")!;
    const [h, c, s] = jwt.split(".");
    const ok = createVerify("RSA-SHA256").update(`${h}.${c}`).verify(publicKey, Buffer.from(s, "base64url"));
    const claim = JSON.parse(Buffer.from(c, "base64url").toString());
    if (!ok || claim.scope !== "https://www.googleapis.com/auth/androidpublisher" || claim.iss !== "svc@x.iam.gserviceaccount.com") {
      res.writeHead(401); res.end("{}"); return;
    }
    res.end(JSON.stringify({ access_token: "AT-1", expires_in: 3600 })); return;
  }
  apiCalls++;
  if (req.headers.authorization !== "Bearer AT-1") { res.writeHead(401); res.end("{}"); return; }
  const m = /applications\/(.+)\/purchases\/products\/(.+)\/tokens\/(.+)$/.exec(req.url!);
  if (!m || m[1] !== "com.hologame.holo") { res.writeHead(404); res.end("{}"); return; }
  if (m[3] === "good") { res.end(JSON.stringify({ purchaseState: 0, consumptionState: 0, orderId: "GPA.9", obfuscatedExternalAccountId: "acc", purchaseType: 0 })); return; }
  if (m[3] === "pend") { res.end(JSON.stringify({ purchaseState: 2, consumptionState: 0, orderId: "GPA.8" })); return; }
  if (m[3] === "err") { res.writeHead(503); res.end("{}"); return; }
  res.writeHead(400); res.end("{}");
});
await new Promise<void>((r) => srv.listen(8811, r));
process.env.GOOGLE_PLAY_SA_JSON = JSON.stringify({ client_email: "svc@x.iam.gserviceaccount.com", private_key: pem, token_uri: "http://127.0.0.1:8811/token" });
process.env.PLAY_API_BASE = "http://127.0.0.1:8811";
const { googleVerifier } = await import("../play.ts");
const g = await googleVerifier("pack_1000", "good");
assert.equal(g!.state, "purchased"); assert.equal(g!.orderId, "GPA.9"); assert.equal(g!.account, "acc"); assert.equal(g!.test, true);
assert.equal((await googleVerifier("pack_1000", "pend"))!.state, "pending");
assert.equal((await googleVerifier("pack_1000", "nonsense"))!.state, "cancelled");
await assert.rejects(googleVerifier("pack_1000", "err"));
assert.equal(tokenCalls, 1, "access token is cached");
delete process.env.GOOGLE_PLAY_SA_JSON;
assert.equal(await googleVerifier("pack_1000", "good"), null, "not configured -> null");
srv.close();
console.log("GOOGLE VERIFIER TEST PASSED", { tokenCalls, apiCalls });
