// In-memory Store for tests (same semantics as store_pg.ts)
export class MemStore {
  players = new Map<string, any>();
  log: any[] = [];
  async ensure() {}
  async saveCloud() {}
  async setRecovery() {}
  async restore() { return null; }
  async linkGoogle(pid: string, gh: string, email: string) {
    for (const [id, pl] of this.players) if (pl.google === gh && id !== pid) return "taken";
    const pl = this.players.get(pid); pl.google = gh; pl.google_email = email; return "ok";
  }
  async restoreGoogle(gh: string) {
    for (const pl of this.players.values()) if (pl.google === gh) return { player: pl, data: pl.save ?? null, bests: [] };
    return null;
  }
  async player(pid: string) { return this.players.get(pid) ?? null; }
  async register(pid: string, secret: string, name: string, country: string) {
    const p = this.players.get(pid);
    if (!p) { this.players.set(pid, { id: pid, secret, name, country, levels: 0, score: 0, stars: 0, diamonds: null, gift: 0 }); return true; }
    return p.secret === secret;
  }
  bests = new Map<string, any>();
  async record(pid: string, level: number, res: any, taps: number[], assists: any[] = []) {
    const p = this.players.get(pid); const k = pid + "|" + level; const cur = this.bests.get(k);
    const improved = !cur || res.level_total > cur.score;
    const r = assists.filter((a) => a[1] === "R" || a[1] === "R2").length, s = assists.filter((a) => a[1] === "S").length;
    if (improved && (r || s)) {
      const rp = this.log.filter((l) => l.pid === pid && l.reason === "spend:revive").length;
      const sp = this.log.filter((l) => l.pid === pid && l.reason === "spend:shield").length;
      p.ru = p.ru ?? 0; p.su = p.su ?? 0;
      if (rp - p.ru < r || sp - p.su < s) return { improved: false, levels: 0, score: 0, stars: 0, unpaid: true };
      p.ru += r; p.su += s;
    }
    if (improved) this.bests.set(k, { level, score: res.level_total, assists, taps, pid });
    const mine = [...this.bests.entries()].filter(([kk]) => kk.startsWith(pid + "|")).map(([, v]) => v);
    p.levels = Math.max(0, ...mine.map((b) => b.level)); p.score = mine.reduce((a, b) => a + b.score, 0);
    return { improved, levels: p.levels, score: p.score, stars: 0 };
  }
  async playerBests() { return []; }
  async ghost(level: number) {
    const b = [...this.bests.values()].filter((v) => v.level === level && !(v.assists ?? []).length)
      .sort((x, y) => y.score - x.score)[0];
    return b ? { id: b.pid, name: this.players.get(b.pid)?.name ?? "", score: b.score, taps: b.taps } : null;
  }
  async ranks() { return { rank: 1, country_rank: 1, levels: 0, score: 0, stars: 0 }; }
  async board() { return { rows: [], total: 0 }; }
  async walletOpen(pid: string, local: number, cap: number, now: number) {
    const p = this.players.get(pid); if (!p) return { balance: 0, imported: null, gift: 0 };
    let imported = null;
    if (p.diamonds === null) { imported = Math.max(0, Math.min(cap, Math.trunc(local))); p.diamonds = imported; this.log.push({ pid, reason: "import", ref: "1", delta: imported, created: now }); }
    const gift = p.gift; if (gift > 0) { p.diamonds += gift; this.log.push({ pid, reason: "gift", ref: now + "-" + gift, delta: gift, created: now }); }
    p.gift = 0;
    return { balance: p.diamonds, imported, gift };
  }
  async walletBalance(pid: string) { const p = this.players.get(pid); return p && p.diamonds !== null ? p.diamonds : null; }
  async walletChange(pid: string, delta: number, reason: string, ref: string, now: number) {
    const p = this.players.get(pid);
    if (this.log.some((l) => l.pid === pid && l.reason === reason && l.ref === ref)) return { ok: true, balance: p.diamonds, dup: true };
    if (p.diamonds + delta < 0) return { ok: false, balance: p.diamonds, dup: false };
    p.diamonds += delta; this.log.push({ pid, reason, ref, delta, created: now });
    return { ok: true, balance: p.diamonds, dup: false };
  }
  async walletSum(pid: string, reason: string, since: number) {
    return this.log.filter((x) => x.pid === pid && x.reason === reason && x.created >= since).reduce((a, x) => a + x.delta, 0);
  }
  endless = new Map<string, any>();
  async endlessRecord(pid: string, week: string, metres: number, steps: number, nonce: string, taps: number[], now: number) {
    const k = week + "|" + pid, cur = this.endless.get(k);
    const wrote = !cur || cur.metres < metres;
    if (wrote) this.endless.set(k, { week, pid, metres, steps, nonce, updated: now });
    const best = Math.max(...[...this.endless.values()].filter((e) => e.pid === pid).map((e) => e.metres));
    return { best, improved: wrote && metres >= best };
  }
  usedRefs = new Set<string>();
  async useAssists(pid: string, revives: number, shields: number, ref: string, _now: number) {
    if (this.usedRefs.has(pid + ref)) return true;
    const p: any = this.players.get(pid);
    if (!p) return false;
    const rp = this.log.filter((x) => x.pid === pid && x.reason === "spend:revive").length;
    const sp = this.log.filter((x) => x.pid === pid && x.reason === "spend:shield").length;
    p.ru = p.ru ?? 0; p.su = p.su ?? 0;
    if (rp - p.ru < revives || sp - p.su < shields) return false;
    p.ru += revives; p.su += shields; this.usedRefs.add(pid + ref);
    return true;
  }
  private endlessSorted(_week: string) {
    const best = new Map<string, any>();
    for (const e of this.endless.values()) {
      const b = best.get(e.pid);
      if (!b || e.metres > b.metres || (e.metres === b.metres && e.updated < b.updated)) best.set(e.pid, e);
    }
    return [...best.values()].sort((a, b) => b.metres - a.metres || a.updated - b.updated);
  }
  async endlessStanding(pid: string, week: string) {
    const all = this.endlessSorted(week), i = all.findIndex((e) => e.pid === pid);
    return i < 0 ? null : { rank: i + 1, metres: all[i].metres, total: all.length };
  }
  async endlessBoard(week: string, offset: number, limit: number) {
    const all = this.endlessSorted(week);
    return { rows: all.slice(offset, offset + limit).map((e, i) => ({ rank: offset + i + 1, id: e.pid, name: this.players.get(e.pid)?.name ?? "?",
                                                                      country: this.players.get(e.pid)?.country ?? "GX", metres: e.metres })),
             total: all.length };
  }
  async walletRefs(pid: string, reason: string, since: number) {
    return this.log.filter((x) => x.pid === pid && x.reason === reason && x.created >= since).map((x) => String(x.ref));
  }
  async walletCount(pid: string, reason: string, since: number) {
    const l = this.log.filter((x) => x.pid === pid && x.reason === reason && x.created >= since);
    return { n: l.length, last: l.reduce((m, x) => Math.max(m, x.created), 0) };
  }
  purchases = new Map<string, any>();
  async walletPurchase(pid: string, th: string, product: string, orderId: string, diamonds: number, now: number) {
    const p = this.players.get(pid);
    const seen = this.purchases.get(th);
    if (seen) return { status: seen.pid === pid ? "dup" : "other_player", balance: p.diamonds };
    this.purchases.set(th, { pid, product, orderId, diamonds });
    if (diamonds > 0) { p.diamonds += diamonds; this.log.push({ pid, reason: "purchase", ref: th, delta: diamonds, created: now }); }
    return { status: "ok", balance: p.diamonds };
  }
  async walletSkins(pid: string) {
    const a = [...this.purchases.values()].filter((x) => x.pid === pid && x.product.startsWith("skin_")).map((x) => x.product.slice(5));
    const b = this.log.filter((l) => l.pid === pid && l.reason.startsWith("spend:skin:")).map((l) => l.reason.slice(11));
    return [...new Set([...a, ...b])];
  }
}
