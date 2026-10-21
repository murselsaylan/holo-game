// The weekly rotation of the shop (shop_items.py is the same code on the game's side; tests/shopx_test.ts compares
// the two against shopx_golden.json). No store, no imports from wallet.ts: wallet.ts uses it for the skin prices.
import { SKIN_COST, SHOPX } from "./wallet_data.ts";

const DAY_S = 86_400;
const X = SHOPX;

/** Monday-based week number of a unix time in ms. */
export const weekIndex = (nowMs: number) => Math.floor((Math.floor(nowMs / 1000 / DAY_S) + 3) / 7);
export const weekEnd = (nowMs: number) => ((weekIndex(nowMs) + 1) * 7 - 3) * DAY_S;      // unix s

const rounded5 = (x: number) => Math.floor(x / 5 + 0.5) * 5;

export function pick<T>(pool: readonly T[], seed: number, count: number): T[] {
  const n = pool.length;
  count = Math.min(count, n);
  const start = (seed * 7919 + 13) % n;
  const step = Math.max(1, Math.floor(n / count));
  const out: number[] = [];
  for (let k = 0; k < count; k++) {
    let i = (start + k * step) % n;
    while (out.includes(i)) i = (i + 1) % n;
    out.push(i);
  }
  return out.map((i) => pool[i]);
}

export const skinPool = () => Object.keys(SKIN_COST).filter((k) => !k.includes("prestige")).sort();

/** The 3 skins of the week at 20 % off: [{skin, price, full}]. */
export function weeklySkins(nowMs: number): { skin: string; price: number; full: number }[] {
  return pick(skinPool(), weekIndex(nowMs), X.WEEKLY_SKINS).map((skin) => {
    const full = (SKIN_COST as Record<string, number>)[skin];
    return { skin, price: rounded5(full * (1 - X.WEEKLY_OFF)), full };
  });
}

export const weeklyFrame = (nowMs: number) => X.LIMITED_FRAMES[weekIndex(nowMs) % X.LIMITED_FRAMES.length];

/** The week's price of a skin or null; a purchase just after the week turned over still gets the old price. */
export function weeklySkinPrice(skin: string, nowMs: number): number | null {
  for (const t of [nowMs, nowMs - 600_000]) {
    const w = weeklySkins(t).find((x) => x.skin === skin);
    if (w) return w.price;
  }
  return null;
}

export interface MarketItem { id: string; kind: string; payload: string | number; stars: number; limit: number }
/** The 3 items of this week's Star Market (one from each pool). */
export function market(nowMs: number): MarketItem[] {
  const wk = weekIndex(nowMs);
  return X.MARKET_POOLS.map((pool, i) => (pool as readonly MarketItem[])[(wk * (3 + i) + i) % pool.length]);
}
