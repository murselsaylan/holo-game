// Supabase Edge Function: HOLO global leaderboard.
// Deploy: supabase functions deploy scores --no-verify-jwt   (the game calls it without a Supabase key)
import postgres from "npm:postgres@3.4.5";
import { handle } from "./handler.ts";
import { PgStore } from "./store_pg.ts";
import { HOME_TEXT, PRIVACY_TEXT } from "./privacy.ts";

const dbUrl = Deno.env.get("DATABASE_URL") ?? Deno.env.get("SUPABASE_DB_URL");
if (!dbUrl) throw new Error("SUPABASE_DB_URL / DATABASE_URL is not set");

// One connection per isolate; prepare:false keeps it compatible with poolers.
const sql = postgres(dbUrl, { max: 1, prepare: false, idle_timeout: 20, connect_timeout: 15 });
const store = new PgStore(sql);

const JSON_HEADERS = { "Content-Type": "application/json; charset=utf-8", "Access-Control-Allow-Origin": "*" };

Deno.serve(async (req: Request) => {
  const url = new URL(req.url);
  const ip = (req.headers.get("x-forwarded-for") ?? "unknown").split(",")[0].trim().slice(0, 64);
  if (req.method === "GET") {                          // public pages (OAuth consent screen / store listing links)
    const p = url.pathname.replace(/\/+$/, "");
    const page = p.endsWith("/privacy") ? PRIVACY_TEXT : (p === "" || p.endsWith("/scores") ? HOME_TEXT : null);
    if (page) return new Response(page, { status: 200, headers: { "Content-Type": "text/plain; charset=utf-8" } });
  }
  try {
    const body = req.method === "POST" ? await req.text() : "";
    const r = await handle(store, req.method, url.pathname, url.searchParams, body, ip);
    return new Response(JSON.stringify(r.body), { status: r.status, headers: JSON_HEADERS });
  } catch (e) {
    console.error("scores error", e);
    return new Response(JSON.stringify({ error: "server error" }), { status: 500, headers: JSON_HEADERS });
  }
});
