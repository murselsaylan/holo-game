// Local test server with the star wallet / daily level (used by tools/ranked_e2e.py).
//   deno run -A --no-check tests/serve_ranked.ts <port> [now-offset-seconds]
import { handle } from "../handler.ts";
import { MemStore } from "./mem.ts";
import { MemRanked } from "./ranked_mem.ts";
import { MemLive } from "./live_mem.ts";

// deno-lint-ignore no-explicit-any
const store: any = new MemStore();
store.live = new MemLive();
store.ranked = new MemRanked((pid: string) => ({ name: store.players.get(pid)?.name ?? "?", country: "TR" }));
const stars = new Map<string, number>();                 // "pid|level" -> best stars (the memory store keeps scores only)
const record = store.record.bind(store);
store.record = async (pid: string, level: number, res: { stars: number }, taps: number[], assists: unknown[]) => {
  const k = pid + "|" + level;
  stars.set(k, Math.max(stars.get(k) ?? 0, res.stars));
  return await record(pid, level, res, taps, assists);
};
store.playerBests = async (pid: string) =>
  [...stars.entries()].filter(([k]) => k.startsWith(pid + "|")).map(([k, v]) => ({ level: Number(k.split("|")[1]), stars: v }));
const port = Number(Deno.args[0] ?? 8787);
const offsetMs = Number(Deno.args[1] ?? 0) * 1000;       // lets a test jump the server clock forward (a new day / week)
Deno.serve({ port, onListen: () => console.log("listening", port) }, async (req: Request) => {
  const url = new URL(req.url);
  const body = req.method === "POST" ? await req.text() : "";
  const r = await handle(store, req.method, url.pathname, url.searchParams, body, "1.1.1." + Math.floor(Math.random() * 250), Date.now() + offsetMs);
  return new Response(JSON.stringify(r.body), { status: r.status, headers: { "Content-Type": "application/json" } });
});
