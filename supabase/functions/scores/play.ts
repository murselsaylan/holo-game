// Google Play purchase verification (Android Publisher API v3) with a service account.
// Secrets (Supabase > Edge Functions > Secrets):
//   GOOGLE_PLAY_SA_JSON   the service account key file (JSON) that has access to the app in the Play Console
//   PLAY_PACKAGE          optional, defaults to com.hologame.holo
//   WALLET_DEV_PURCHASES  optional "1": accept "dev-" tokens from test builds (never set this in production)
const env = (k: string) => (globalThis as any).Deno?.env?.get?.(k) ?? (globalThis as any).process?.env?.[k];

export const PLAY_PACKAGE = () => env("PLAY_PACKAGE") || "com.hologame.holo";
export const devPurchases = () => env("WALLET_DEV_PURCHASES") === "1";

export interface PlayPurchase {
  state: "purchased" | "pending" | "cancelled";
  orderId: string;
  account: string;          // obfuscatedExternalAccountId set by the game at checkout
  consumed: boolean;
  test: boolean;
}

export type Verifier = (productId: string, token: string) => Promise<PlayPurchase | null>;   // null = not configured

let cached: { token: string; exp: number } | null = null;

function b64url(data: Uint8Array | string): string {
  const bytes = typeof data === "string" ? new TextEncoder().encode(data) : data;
  let s = "";
  for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

async function accessToken(sa: { client_email: string; private_key: string; token_uri?: string }): Promise<string> {
  const now = Math.floor(Date.now() / 1000);
  if (cached && cached.exp - 120 > now) return cached.token;
  const pem = sa.private_key.replace(/-----[^-]+-----/g, "").replace(/\s+/g, "");
  const der = Uint8Array.from(atob(pem), (c) => c.charCodeAt(0));
  const key = await crypto.subtle.importKey("pkcs8", der, { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, ["sign"]);
  const aud = sa.token_uri || "https://oauth2.googleapis.com/token";
  const head = b64url(JSON.stringify({ alg: "RS256", typ: "JWT" }));
  const claim = b64url(JSON.stringify({ iss: sa.client_email, scope: "https://www.googleapis.com/auth/androidpublisher",
                                        aud, iat: now, exp: now + 3600 }));
  const sig = new Uint8Array(await crypto.subtle.sign("RSASSA-PKCS1-v1_5", key, new TextEncoder().encode(`${head}.${claim}`)));
  const r = await fetch(aud, { method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: `grant_type=${encodeURIComponent("urn:ietf:params:oauth:grant-type:jwt-bearer")}&assertion=${head}.${claim}.${b64url(sig)}` });
  if (!r.ok) throw new Error(`google oauth ${r.status}`);
  const j = await r.json();
  cached = { token: j.access_token, exp: now + Number(j.expires_in ?? 3600) };
  return cached.token;
}

/** Asks Google about a one-time product purchase. Throws on network / API trouble (the game retries later). */
export const googleVerifier: Verifier = async (productId, token) => {
  const raw = env("GOOGLE_PLAY_SA_JSON");
  if (!raw) return null;
  const sa = JSON.parse(raw);
  const base = env("PLAY_API_BASE") || "https://androidpublisher.googleapis.com";    // overridden only by tests
  const url = `${base}/androidpublisher/v3/applications/${encodeURIComponent(PLAY_PACKAGE())}` +
    `/purchases/products/${encodeURIComponent(productId)}/tokens/${encodeURIComponent(token)}`;
  const r = await fetch(url, { headers: { Authorization: `Bearer ${await accessToken(sa)}` } });
  if (r.status === 404 || r.status === 410 || r.status === 400) {
    return { state: "cancelled", orderId: "", account: "", consumed: false, test: false };   // unknown / invalid token
  }
  if (!r.ok) throw new Error(`play api ${r.status}`);
  const p = await r.json();
  const st = Number(p.purchaseState);
  return {
    state: st === 0 ? "purchased" : st === 2 ? "pending" : "cancelled",
    orderId: String(p.orderId ?? ""),
    account: String(p.obfuscatedExternalAccountId ?? ""),
    consumed: Number(p.consumptionState) === 1,
    test: Number(p.purchaseType) === 0,
  };
};
