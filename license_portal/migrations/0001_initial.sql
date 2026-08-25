CREATE TABLE IF NOT EXISTS licenses (
    id TEXT PRIMARY KEY,
    key_hmac TEXT NOT NULL UNIQUE,
    license_type TEXT NOT NULL CHECK (license_type IN ('time', 'perpetual')),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'revoked')),
    expires_at TEXT,
    max_devices INTEGER NOT NULL DEFAULT 1 CHECK (max_devices >= 1 AND max_devices <= 10),
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    revoked_at TEXT
);

CREATE TABLE IF NOT EXISTS activations (
    id TEXT PRIMARY KEY,
    license_id TEXT NOT NULL REFERENCES licenses(id) ON DELETE CASCADE,
    device_hmac TEXT NOT NULL,
    device_label TEXT NOT NULL DEFAULT '',
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    revoked_at TEXT,
    UNIQUE (license_id, device_hmac)
);

CREATE INDEX IF NOT EXISTS idx_activations_license_id ON activations(license_id);

CREATE TABLE IF NOT EXISTS license_events (
    id TEXT PRIMARY KEY,
    license_id TEXT REFERENCES licenses(id) ON DELETE SET NULL,
    event_type TEXT NOT NULL,
    event_note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_license_events_license_id ON license_events(license_id, created_at DESC);

CREATE TABLE IF NOT EXISTS rate_limits (
    scope TEXT PRIMARY KEY,
    window_started_at INTEGER NOT NULL,
    attempt_count INTEGER NOT NULL,
    blocked_until INTEGER NOT NULL DEFAULT 0
);
