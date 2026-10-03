// "Sign in with Google" ID tokens (Android Credential Manager): the account a pilot is linked to, for recovery.
// Checked here: RS256 signature against Google's published keys, issuer, audience = our Web client id, expiry.
// Config (Supabase secrets / env):
//   GOOGLE_WEB_CLIENT_ID   the OAuth "Web application" client id the game asks tokens for (comma-separated for several)
//   GOOGLE_CERTS_URL       tests only: where the JWKS comes from
const env = (k: string) => (globalThis as any).Deno?.env?.get?.(k) ?? (globalThis as any).process?.env?.[k];

export interface GoogleIdentity { sub: string; email: string }

let keys: { at: number; byKid: Map<string, CryptoKey> } | null = null;

function b64urlBytes(s: string): Uint8Array {
  s = s.replace(/-/g, "+").replace(/_/g, "/");
  while (s.length % 4) s += "=";
  return Uint8Array.from(atob(s), (c) => c.charCodeAt(0));
}

async function googleKeys(nowMs: number, force = false): Promise<Map<string, CryptoKey>> {
  if (keys && !force && nowMs - keys.at < 3_600_000) return keys.byKid;
  const r = await fetch(env("GOOGLE_CERTS_URL") || "https://www.googleapis.com/oauth2/v3/certs");
  if (!r.ok) throw new Error(`google certs ${r.status}`);
  const j = await r.json();
  const byKid = new Map<string, CryptoKey>();
  for (const k of j.keys ?? []) {
    if (k.kty !== "RSA") continue;
    byKid.set(k.kid, await crypto.subtle.importKey("jwk", { kty: "RSA", n: k.n, e: k.e, alg: "RS256", ext: true },
                                                     { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, ["verify"]));
  }
  keys = { at: nowMs, byKid };
  return byKid;
}

export const googleConfigured = () => Boolean(String(env("GOOGLE_WEB_CLIENT_ID") ?? "").trim());

/** The Google account behind an ID token, or null (bad / expired / not for this app). Throws only on network trouble. */
export async function verifyGoogleIdToken(token: string, nowMs = Date.now()): Promise<GoogleIdentity | null> {
  const audiences = String(env("GOOGLE_WEB_CLIENT_ID") ?? "").split(",").map((s) => s.trim()).filter(Boolean);
  if (!audiences.length || typeof token !== "string" || token.length > 4096) return null;
  const parts = token.split(".");
  if (parts.length !== 3) return null;
  let head: any, claims: any;
  try {
    head = JSON.parse(new TextDecoder().decode(b64urlBytes(parts[0])));
    claims = JSON.parse(new TextDecoder().decode(b64urlBytes(parts[1])));
  } catch {
    return null;
  }
  if (head.alg !== "RS256" || typeof head.kid !== "string") return null;
  let byKid = await googleKeys(nowMs);
  if (!byKid.has(head.kid)) byKid = await googleKeys(nowMs, true);     // Google rotated its keys
  const key = byKid.get(head.kid);
  if (!key) return null;
  const ok = await crypto.subtle.verify("RSASSA-PKCS1-v1_5", key, b64urlBytes(parts[2]),
                                        new TextEncoder().encode(`${parts[0]}.${parts[1]}`));
  if (!ok) return null;
  const now = nowMs / 1000;
  if (claims.iss !== "https://accounts.google.com" && claims.iss !== "accounts.google.com") return null;
  const aud = Array.isArray(claims.aud) ? claims.aud : [claims.aud];
  if (!aud.some((a: string) => audiences.includes(a))) return null;
  if (!(Number(claims.exp) > now - 60) || Number(claims.iat) > now + 300) return null;
  if (typeof claims.sub !== "string" || !claims.sub) return null;
  if (claims.email && claims.email_verified === false) return null;
  return { sub: claims.sub, email: String(claims.email ?? "") };
}

/** "mu****5@gmail.com": enough for the player to recognise the account, not a readable address. */
export function maskEmail(email: string): string {
  const [user, domain] = email.split("@");
  if (!user || !domain) return "";
  const keep = user.length <= 2 ? user.slice(0, 1) : user.slice(0, 2);
  return `${keep}${"*".repeat(Math.max(2, user.length - keep.length - 1))}${user.length > 3 ? user.slice(-1) : ""}@${domain}`;
}
