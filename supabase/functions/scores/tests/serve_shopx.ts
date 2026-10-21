// Local test server for tools/shopx_e2e.py: serve_ranked.ts plus a test-only backdoor that hands stars to a player
// (POST /dev/stars {pid, n}) - the real server has no such route. Never deployed (only tests/ is run locally).
//   deno run -A --no-check tests/serve_shopx.ts <port> [now-offset-seconds]
import { handle } from "../handler.ts";
import { MemStore } from "./mem.ts";
import { MemRanked } from "./ranked_mem.ts";
import { MemLive } from "./live_mem.ts";

// deno-lint-ignore no-explicit-any
const store: any = new MemStore();
store.live = new MemLive();
store.ranked = new MemRanked((pid: string) => ({ name: store.players.get(pid)?.name ?? "?", country: "TR" }));
const port = Number(Deno.args[0] ?? 8787);
const offsetMs = Number(Deno.args[1] ?? 0) * 1000;
let n = 0;
Deno.serve({ port, onListen: () => console.log("listening", port) }, async (req: Request) => {
  const url = new URL(req.url);
  const body = req.method === "POST" ? await req.text() : "";
  if (url.pathname === "/dev/stars" || url.pathname === "/dev/grant") {
    // body {pid?, stars?, gems?} (/dev/stars: {pid, n} = stars); no pid = every player that has opened a wallet
    const d = JSON.parse(body || "{}");
    const stars = Number(d.stars ?? (url.pathname === "/dev/stars" ? d.n : 0) ?? 0) || 0, gems = Number(d.gems ?? 0) || 0;
    const ids = d.pid ? [String(d.pid)] : [...store.players.keys()];
    if (d.reset) {                                  // {"reset": true}: today's chest / market / pack limits start again
      store.ranked.stars = store.ranked.stars.filter((x: any) => !(ids.includes(x.pid) && /^spend:(chest|mkt)/.test(x.reason)));
      store.log = store.log.filter((x: any) => !(ids.includes(x.pid) && /^spend:pack/.test(x.reason)));
    }
    const now = Math.floor((Date.now() + offsetMs) / 1000);
    for (const pid of ids) {
      if (stars) await store.ranked.starChange(pid, stars, "endless", "dev" + (n++), now);
      if (gems && (await store.walletBalance(pid)) !== null) await store.walletChange(pid, gems, "dev", "dev" + (n++), now);
    }
    return new Response(JSON.stringify({ players: ids.length }));
  }
  const r = await handle(store, req.method, url.pathname, url.searchParams, body, "1.1.1." + Math.floor(Math.random() * 250), Date.now() + offsetMs);
  return new Response(JSON.stringify(r.body), { status: r.status, headers: { "Content-Type": "application/json" } });
});
