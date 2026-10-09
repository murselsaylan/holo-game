// App Store purchase verification (StoreKit on iOS). The game sends token "ios:<transactionId>" and the app receipt.
// Secrets (Supabase > Edge Functions > Secrets):
//   APPLE_IAP_KEY        the In-App Purchase key (.p8 text) from App Store Connect > Users and Access > Integrations
//   APPLE_IAP_KEY_ID     its key id
//   APPLE_ISSUER_ID      the issuer id shown on that page
//   APPLE_BUNDLE_ID      optional, defaults to com.hologame.holo
// With the key the App Store Server API answers for the transaction itself ("Get Transaction Info"). Without it the
// older receipt check (verifyReceipt, no secret needed for one-time products) is used, so purchases work either way.
import type { PlayPurchase } from "./play.ts";

const env = (k: string) => (globalThis as any).Deno?.env?.get?.(k) ?? (globalThis as any).process?.env?.[k];
export const APPLE_BUNDLE = () => env("APPLE_BUNDLE_ID") || "com.hologame.holo";

export type AppleVerifier = (productId: string, transactionId: string, receipt: string) => Promise<PlayPurchase | null>;

function b64url(data: Uint8Array | string): string {
  const bytes = typeof data === "string" ? new TextEncoder().encode(data) : data;
  let s = "";
  for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function b64urlDecode(s: string): string {
  const pad = s.replace(/-/g, "+").replace(/_/g, "/") + "===".slice((s.length + 3) % 4);
  const bin = atob(pad);
  return new TextDecoder().decode(Uint8Array.from(bin, (c) => c.charCodeAt(0)));
}

async function serverToken(): Promise<string | null> {
  const p8 = env("APPLE_IAP_KEY"), kid = env("APPLE_IAP_KEY_ID"), iss = env("APPLE_ISSUER_ID");
  if (!p8 || !kid || !iss) return null;
  const pem = String(p8).replace(/-----[^-]+-----/g, "").replace(/\\n/g, "").replace(/\s+/g, "");
  const der = Uint8Array.from(atob(pem), (c) => c.charCodeAt(0));
  const key = await crypto.subtle.importKey("pkcs8", der, { name: "ECDSA", namedCurve: "P-256" }, false, ["sign"]);
  const now = Math.floor(Date.now() / 1000);
  const head = b64url(JSON.stringify({ alg: "ES256", kid, typ: "JWT" }));
  const claim = b64url(JSON.stringify({ iss, iat: now, exp: now + 1800, aud: "appstoreconnect-v1", bid: APPLE_BUNDLE() }));
  const sig = new Uint8Array(await crypto.subtle.sign({ name: "ECDSA", hash: "SHA-256" }, key,
                                                     new TextEncoder().encode(`${head}.${claim}`)));
  return `${head}.${claim}.${b64url(sig)}`;     // WebCrypto ECDSA signatures are already raw r||s (what JWT wants)
}

const API = () => env("APPLE_API_BASE");      // tests only
const PROD = "https://api.storekit.itunes.apple.com", SANDBOX = "https://api.storekit-sandbox.itunes.apple.com";

function judge(productId: string, t: Record<string, unknown> | undefined, env_: string): PlayPurchase {
  const bad: PlayPurchase = { state: "cancelled", orderId: "", account: "", consumed: false, test: false };
  if (!t) return bad;
  const bundle = String(t.bundleId ?? t.bid ?? APPLE_BUNDLE());
  const product = String(t.productId ?? t.product_id ?? "");
  if (bundle !== APPLE_BUNDLE() || product !== productId) return bad;
  if (t.revocationDate || t.cancellation_date || t.cancellation_date_ms) return bad;
  const tid = String(t.transactionId ?? t.transaction_id ?? "");
  return { state: "purchased", orderId: "APPLE." + tid, account: "", consumed: false, test: env_ !== "Production" };
}

async function viaServerApi(token: string, productId: string, tid: string): Promise<PlayPurchase> {
  for (const base of API() ? [API()] : [PROD, SANDBOX]) {
    const r = await fetch(`${base}/inApps/v1/transactions/${encodeURIComponent(tid)}`,
                          { headers: { Authorization: `Bearer ${token}` } });
    if (r.status === 404) continue;                                  // not in this environment: try the sandbox
    if (r.status === 400) break;                                     // malformed id
    if (!r.ok) throw new Error(`app store api ${r.status}`);
    const j = await r.json();
    const parts = String(j.signedTransactionInfo ?? "").split(".");
    if (parts.length !== 3) break;
    // straight from Apple over TLS with our own key, so the payload can be read without checking the JWS chain
    const t = JSON.parse(b64urlDecode(parts[1]));
    return judge(productId, t, String(t.environment ?? (base === PROD ? "Production" : "Sandbox")));
  }
  return { state: "cancelled", orderId: "", account: "", consumed: false, test: false };
}

async function viaReceipt(receipt: string, productId: string, tid: string): Promise<PlayPurchase | null> {
  if (!receipt) return null;
  for (const url of API() ? [`${API()}/verifyReceipt`] : ["https://buy.itunes.apple.com/verifyReceipt",
                                                           "https://sandbox.itunes.apple.com/verifyReceipt"]) {
    const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" },
                                 body: JSON.stringify({ "receipt-data": receipt, "exclude-old-transactions": false }) });
    if (!r.ok) throw new Error(`verifyReceipt ${r.status}`);
    const j = await r.json();
    const status = Number(j.status);
    if (status === 21007) continue;                                  // a sandbox receipt: ask the sandbox
    if (status === 21005 || status === 21009 || (status >= 21100 && status <= 21199)) throw new Error(`receipt ${status}`);
    if (status !== 0) break;
    const rec = j.receipt ?? {};
    if (String(rec.bundle_id ?? "") !== APPLE_BUNDLE()) break;
    const items = [...(rec.in_app ?? []), ...(j.latest_receipt_info ?? [])] as Record<string, unknown>[];
    const t = items.find((x) => String(x.transaction_id) === tid);
    return judge(productId, t ? { ...t, bundleId: rec.bundle_id } : undefined,
                 String(j.environment ?? "Production"));
  }
  return { state: "cancelled", orderId: "", account: "", consumed: false, test: false };
}

export const appleVerifier: AppleVerifier = async (productId, transactionId, receipt) => {
  if (!/^\d{1,30}$/.test(transactionId)) return { state: "cancelled", orderId: "", account: "", consumed: false, test: false };
  const token = await serverToken();
  if (token) return await viaServerApi(token, productId, transactionId);
  return await viaReceipt(receipt, productId, transactionId);
};
