// Local test server: the real request handler on an in-memory store (used by tools/friends_e2e.py).
//   deno run -A --no-check tests/serve_mem.ts <port>
import { handle } from "../handler.ts";
import { MemStore } from "./mem.ts";

const store = new MemStore();
const port = Number(Deno.args[0] ?? 8787);
Deno.serve({ port, onListen: () => console.log("listening", port) }, async (req: Request) => {
  const url = new URL(req.url);
  const body = req.method === "POST" ? await req.text() : "";
  const r = await handle(store as any, req.method, url.pathname, url.searchParams, body, "1.1.1." + Math.floor(Math.random() * 250));
  return new Response(JSON.stringify(r.body), { status: r.status, headers: { "Content-Type": "application/json" } });
});
