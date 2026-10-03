-- HOLO leaderboard schema (Supabase Postgres). Run once; the `scores` edge function no longer creates it on start.
CREATE TABLE IF NOT EXISTS players(
  id TEXT PRIMARY KEY, secret TEXT NOT NULL, name TEXT NOT NULL, country TEXT NOT NULL,
  levels INTEGER NOT NULL DEFAULT 0, score INTEGER NOT NULL DEFAULT 0, stars INTEGER NOT NULL DEFAULT 0,
  created BIGINT NOT NULL, updated BIGINT NOT NULL);
CREATE TABLE IF NOT EXISTS bests(
  player_id TEXT NOT NULL, level INTEGER NOT NULL, score INTEGER NOT NULL, stars INTEGER NOT NULL,
  "time" DOUBLE PRECISION NOT NULL, swaps INTEGER NOT NULL, "rank" TEXT NOT NULL, taps TEXT NOT NULL, updated BIGINT NOT NULL,
  PRIMARY KEY(player_id, level));
CREATE INDEX IF NOT EXISTS idx_rank ON players(levels DESC, score DESC);
CREATE INDEX IF NOT EXISTS idx_country ON players(country, levels DESC, score DESC);
-- The function talks to Postgres with the service credentials only; keep the tables closed to the public REST API.
ALTER TABLE players ENABLE ROW LEVEL SECURITY;
ALTER TABLE bests ENABLE ROW LEVEL SECURITY;
-- Account recovery (1.0.2): hash of the pilot's recovery code + a cloud copy of the save file.
ALTER TABLE players ADD COLUMN IF NOT EXISTS recovery TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS idx_recovery ON players(recovery) WHERE recovery IS NOT NULL;
CREATE TABLE IF NOT EXISTS saves(player_id TEXT PRIMARY KEY, data TEXT NOT NULL, updated BIGINT NOT NULL);
ALTER TABLE saves ENABLE ROW LEVEL SECURITY;
CREATE INDEX IF NOT EXISTS idx_score ON players(score DESC, levels DESC);   -- ranking = total score, then highest level

-- Diamond wallet (1.0.3): the server owns every player's diamond balance.
ALTER TABLE players ADD COLUMN IF NOT EXISTS diamonds INTEGER;            -- NULL = wallet not opened yet (old client)
ALTER TABLE players ADD COLUMN IF NOT EXISTS gift INTEGER NOT NULL DEFAULT 0;   -- diamonds handed out on the next sync
CREATE TABLE IF NOT EXISTS wallet_log(
  id BIGSERIAL PRIMARY KEY,
  player_id TEXT NOT NULL,
  delta INTEGER NOT NULL,
  balance INTEGER NOT NULL,
  reason TEXT NOT NULL,
  ref TEXT NOT NULL,
  created BIGINT NOT NULL,
  UNIQUE(player_id, reason, ref));
CREATE INDEX IF NOT EXISTS idx_wallet_player ON wallet_log(player_id, reason, created);
ALTER TABLE wallet_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE players DROP CONSTRAINT IF EXISTS diamonds_not_negative;
ALTER TABLE players ADD CONSTRAINT diamonds_not_negative CHECK (diamonds IS NULL OR diamonds >= 0);

-- Verified Google Play purchases: one row per purchase token (hashed), so a token can never be credited twice.
CREATE TABLE IF NOT EXISTS purchases(
  token_hash TEXT PRIMARY KEY,
  player_id TEXT NOT NULL,
  product TEXT NOT NULL,
  order_id TEXT NOT NULL,
  diamonds INTEGER NOT NULL,
  created BIGINT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_purchases_player ON purchases(player_id);
ALTER TABLE purchases ENABLE ROW LEVEL SECURITY;

-- paid help (revive / shield) in ranked runs (applied 2026-09-28)
ALTER TABLE players ADD COLUMN IF NOT EXISTS assist_revives_used INTEGER NOT NULL DEFAULT 0;
ALTER TABLE players ADD COLUMN IF NOT EXISTS assist_shields_used INTEGER NOT NULL DEFAULT 0;
ALTER TABLE bests ADD COLUMN IF NOT EXISTS assists TEXT NOT NULL DEFAULT '';

-- endless climb (1.0.5): each player's best height per ISO week; the taps are kept so a run can be re-checked
CREATE TABLE IF NOT EXISTS endless_bests (
  week TEXT NOT NULL,
  player_id TEXT NOT NULL REFERENCES players(id) ON DELETE CASCADE,
  metres INTEGER NOT NULL,
  steps INTEGER NOT NULL,
  nonce TEXT NOT NULL,
  taps TEXT NOT NULL,
  updated BIGINT NOT NULL,
  PRIMARY KEY (week, player_id)
);
CREATE INDEX IF NOT EXISTS idx_endless_week ON endless_bests (week, metres DESC, updated ASC);

-- account recovery through a Google account (1.0.5): hash of the Google account id + a masked address for display
ALTER TABLE players ADD COLUMN IF NOT EXISTS google TEXT;
ALTER TABLE players ADD COLUMN IF NOT EXISTS google_email TEXT NOT NULL DEFAULT '';
CREATE UNIQUE INDEX IF NOT EXISTS idx_players_google ON players (google) WHERE google IS NOT NULL;
