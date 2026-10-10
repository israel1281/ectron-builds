CREATE TABLE IF NOT EXISTS hosts (
  device_key TEXT PRIMARY KEY,
  id TEXT NOT NULL,
  name TEXT NOT NULL,
  platform TEXT NOT NULL,
  last_seen INTEGER NOT NULL
);
