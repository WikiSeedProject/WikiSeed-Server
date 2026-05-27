-- WikiSeed-Server schema. Loaded automatically by the postgres container on first
-- start via docker-entrypoint-initdb.d.

CREATE TABLE IF NOT EXISTS dumps (
    id                    SERIAL PRIMARY KEY,
    wiki_or_project       TEXT NOT NULL,
    language              TEXT,
    source_type           TEXT NOT NULL
        CHECK (source_type IN ('xml_current', 'xml_history', 'zim')),
    zim_scope             TEXT CHECK (zim_scope IN ('maxi', 'nopic', 'mini')),
    zim_topic             TEXT,
    period                TEXT NOT NULL,
    discovered_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sha256_wikimedia      TEXT,
    sha256_wikiseed       TEXT,
    filesize_bytes        BIGINT,
    wikimedia_url         TEXT NOT NULL UNIQUE,
    download_status       TEXT NOT NULL DEFAULT 'pending'
        CHECK (download_status IN ('pending', 'downloading', 'completed', 'failed')),
    download_completed_at TIMESTAMPTZ,
    ia_item_id            TEXT,
    ia_url                TEXT,
    ia_confirmed_at       TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_dumps_status   ON dumps(download_status);
CREATE INDEX IF NOT EXISTS idx_dumps_source   ON dumps(source_type, period);
CREATE INDEX IF NOT EXISTS idx_dumps_grouping ON dumps(wiki_or_project, source_type, period, zim_scope);

CREATE TABLE IF NOT EXISTS torrents (
    id                     SERIAL PRIMARY KEY,
    torrent_name           TEXT NOT NULL UNIQUE,
    info_hash              TEXT UNIQUE,
    magnet_link            TEXT,
    torrent_file_path      TEXT,
    torrent_file_r2_key    TEXT,
    source_type            TEXT NOT NULL,
    project                TEXT NOT NULL,
    zim_scope              TEXT,
    period                 TEXT NOT NULL,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    total_size_bytes       BIGINT,
    seeder_count           INT NOT NULL DEFAULT 0,
    last_seeder_check      TIMESTAMPTZ,
    health_status          TEXT NOT NULL DEFAULT 'unknown'
        CHECK (health_status IN ('healthy', 'warning', 'recovering', 'unknown')),
    below_threshold_since  TIMESTAMPTZ,
    ia_confirmed           BOOLEAN NOT NULL DEFAULT FALSE,
    eligible_for_deletion  BOOLEAN NOT NULL DEFAULT FALSE,
    local_files_deleted_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_torrents_health   ON torrents(health_status);
CREATE INDEX IF NOT EXISTS idx_torrents_eligible ON torrents(eligible_for_deletion);

CREATE TABLE IF NOT EXISTS torrent_dumps (
    torrent_id INT NOT NULL REFERENCES torrents(id) ON DELETE CASCADE,
    dump_id    INT NOT NULL REFERENCES dumps(id)    ON DELETE CASCADE,
    PRIMARY KEY (torrent_id, dump_id)
);

CREATE TABLE IF NOT EXISTS health_events (
    id           SERIAL PRIMARY KEY,
    torrent_id   INT NOT NULL REFERENCES torrents(id) ON DELETE CASCADE,
    event_type   TEXT NOT NULL
        CHECK (event_type IN ('below_threshold', 'redownload_triggered', 'recovered', 'deleted')),
    seeder_count INT,
    timestamp    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    notes        TEXT
);

CREATE INDEX IF NOT EXISTS idx_health_events_torrent ON health_events(torrent_id, timestamp DESC);

CREATE TABLE IF NOT EXISTS jobs (
    id           SERIAL PRIMARY KEY,
    job_type     TEXT NOT NULL,
    payload      JSONB NOT NULL DEFAULT '{}'::jsonb,
    status       TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at   TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    retry_count  INT NOT NULL DEFAULT 0,
    last_error   TEXT
);

-- Partial index makes claim() cheap: scan only pending rows of the requested type.
CREATE INDEX IF NOT EXISTS idx_jobs_pending ON jobs(job_type, created_at) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_jobs_status  ON jobs(status);

-- Persists the controller's last-run timestamps across restarts so periodic
-- tasks fire once per scheduled window, not once per container restart.
CREATE TABLE IF NOT EXISTS scheduler_state (
    task     TEXT PRIMARY KEY,
    last_run TIMESTAMPTZ NOT NULL
);
