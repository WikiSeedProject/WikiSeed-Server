-- WikiSeed Initial Schema Migration
-- Version: 1

-- Enable foreign keys and configure SQLite
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;

-- System state table
CREATE TABLE IF NOT EXISTS system_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_system_state_updated ON system_state(updated_at);

-- Insert initial system state
INSERT OR IGNORE INTO system_state (key, value) VALUES
    ('schema_version', '1'),
    ('system_health', 'healthy');

-- Dumps table
CREATE TABLE IF NOT EXISTS dumps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project TEXT NOT NULL,
    language TEXT NOT NULL,
    wiki_db_name TEXT NOT NULL,
    cycle_date DATE NOT NULL,
    dump_type TEXT NOT NULL,
    filename TEXT NOT NULL,
    is_history BOOLEAN DEFAULT 0,
    size_bytes INTEGER,
    md5 TEXT,
    sha1 TEXT,
    sha256 TEXT,
    wikimedia_url TEXT NOT NULL,
    local_path TEXT,
    ia_identifier TEXT,
    ia_url TEXT,
    archive_today_url TEXT,
    wikimedia_status TEXT,
    our_status TEXT DEFAULT 'pending',
    wikimedia_date TIMESTAMP,
    discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    downloaded_at TIMESTAMP,
    uploaded_at TIMESTAMP,
    error_message TEXT,
    UNIQUE(wiki_db_name, cycle_date, filename)
);

CREATE INDEX IF NOT EXISTS idx_dumps_cycle ON dumps(cycle_date);
CREATE INDEX IF NOT EXISTS idx_dumps_wiki ON dumps(wiki_db_name, cycle_date);
CREATE INDEX IF NOT EXISTS idx_dumps_status ON dumps(our_status);
CREATE INDEX IF NOT EXISTS idx_dumps_project_lang ON dumps(project, language);
CREATE INDEX IF NOT EXISTS idx_dumps_type ON dumps(dump_type);

-- Jobs table
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_type TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    parent_job_id INTEGER,
    dump_id INTEGER,
    cycle_date DATE,
    params TEXT,
    result TEXT,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 5,
    next_retry_at TIMESTAMP,
    last_error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    logs_path TEXT,
    FOREIGN KEY (parent_job_id) REFERENCES jobs(id) ON DELETE SET NULL,
    FOREIGN KEY (dump_id) REFERENCES dumps(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_jobs_type_status ON jobs(job_type, status);
CREATE INDEX IF NOT EXISTS idx_jobs_parent ON jobs(parent_job_id);
CREATE INDEX IF NOT EXISTS idx_jobs_dump ON jobs(dump_id);
CREATE INDEX IF NOT EXISTS idx_jobs_cycle ON jobs(cycle_date);
CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at);
CREATE INDEX IF NOT EXISTS idx_jobs_next_retry ON jobs(next_retry_at) WHERE status = 'pending' AND next_retry_at IS NOT NULL;

-- Torrents table
CREATE TABLE IF NOT EXISTS torrents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    filename TEXT NOT NULL,
    cycle_date DATE NOT NULL,
    is_compressed BOOLEAN DEFAULT 1,
    is_history BOOLEAN DEFAULT 0,
    info_hash TEXT NOT NULL UNIQUE,
    magnet_link TEXT NOT NULL,
    piece_size_bytes INTEGER,
    piece_count INTEGER,
    total_size_bytes INTEGER,
    file_count INTEGER,
    torrent_file_path TEXT NOT NULL,
    torrent_url TEXT,
    trackers TEXT,
    webseeds TEXT,
    published BOOLEAN DEFAULT 0,
    published_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(cycle_date, is_compressed, is_history)
);

CREATE INDEX IF NOT EXISTS idx_torrents_cycle ON torrents(cycle_date);
CREATE INDEX IF NOT EXISTS idx_torrents_published ON torrents(published);
CREATE INDEX IF NOT EXISTS idx_torrents_hash ON torrents(info_hash);

-- Torrent files (many-to-many)
CREATE TABLE IF NOT EXISTS torrent_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    torrent_id INTEGER NOT NULL,
    dump_id INTEGER NOT NULL,
    path_in_torrent TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    FOREIGN KEY (torrent_id) REFERENCES torrents(id) ON DELETE CASCADE,
    FOREIGN KEY (dump_id) REFERENCES dumps(id) ON DELETE CASCADE,
    UNIQUE(torrent_id, dump_id)
);

CREATE INDEX IF NOT EXISTS idx_torrent_files_torrent ON torrent_files(torrent_id);
CREATE INDEX IF NOT EXISTS idx_torrent_files_dump ON torrent_files(dump_id);

-- Torrent statistics
CREATE TABLE IF NOT EXISTS torrent_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    torrent_id INTEGER NOT NULL,
    seeders INTEGER DEFAULT 0,
    leechers INTEGER DEFAULT 0,
    completed INTEGER DEFAULT 0,
    source TEXT,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (torrent_id) REFERENCES torrents(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_torrent_stats_torrent ON torrent_stats(torrent_id, recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_torrent_stats_recorded ON torrent_stats(recorded_at);
