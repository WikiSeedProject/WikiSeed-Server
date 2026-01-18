# WikiSeed: Database Schema

## Overview

WikiSeed uses **SQLite** for its job queue and state management. This document describes the complete database schema, indexes, relationships, and migration strategy.

## Technology

- **Database**: SQLite 3.35+ (for JSON support and modern features)
- **Location**: `/data/db/jobs.db`
- **Journal Mode**: WAL (Write-Ahead Logging) for better concurrency
- **Migrations**: Versioned SQL scripts in `migrations/` directory

## Schema Version

Current schema version: **1**

Schema version is tracked in the `system_state` table.

## Database Configuration

```sql
-- Applied at connection time
PRAGMA journal_mode = WAL;          -- Better concurrency for multi-container access
PRAGMA synchronous = NORMAL;        -- Balance safety and performance
PRAGMA foreign_keys = ON;           -- Enforce foreign key constraints
PRAGMA cache_size = 10000;          -- ~10MB cache
PRAGMA temp_store = MEMORY;         -- Temp tables in RAM
```

## Tables

### 1. system_state

Stores system-level metadata and configuration state.

```sql
CREATE TABLE system_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_system_state_updated ON system_state(updated_at);
```

**Common Keys**:
- `schema_version`: Current database schema version (e.g., "1")
- `current_cycle_date`: Active cycle being processed (e.g., "2026-01-20")
- `last_publish_date`: Most recent publish date
- `system_health`: Overall system status (e.g., "healthy", "degraded", "error")
- `last_scrape_time`: Timestamp of last Wikimedia scrape
- `total_dumps_processed`: Lifetime count of dumps processed

**Example Data**:
```sql
INSERT INTO system_state (key, value) VALUES
    ('schema_version', '1'),
    ('current_cycle_date', '2026-01-20'),
    ('last_publish_date', '2026-01-19'),
    ('system_health', 'healthy');
```

---

### 2. dumps

Stores metadata for individual dump files (one row per file).

```sql
CREATE TABLE dumps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Wiki identification
    project TEXT NOT NULL,              -- 'wikipedia', 'wiktionary', 'wikisource', etc.
    language TEXT NOT NULL,             -- 'en', 'fr', 'de', etc.
    wiki_db_name TEXT NOT NULL,         -- 'enwiki', 'frwiki', etc.

    -- Dump identification
    cycle_date DATE NOT NULL,           -- '2026-01-20'
    dump_type TEXT NOT NULL,            -- 'pages-articles', 'pages-meta-history', etc.
    filename TEXT NOT NULL,             -- 'enwiki-20260120-pages-articles1.xml.bz2'
    is_history BOOLEAN DEFAULT 0,       -- 1 if full history dump, 0 if regular

    -- File metadata
    size_bytes INTEGER,                 -- File size in bytes
    md5 TEXT,                           -- MD5 hash from Wikimedia
    sha1 TEXT,                          -- SHA1 hash from Wikimedia
    sha256 TEXT,                        -- SHA256 hash (we generate this)

    -- URLs and locations
    wikimedia_url TEXT NOT NULL,        -- Original download URL
    local_path TEXT,                    -- Local filesystem path after download
    ia_identifier TEXT,                 -- Internet Archive item identifier
    ia_url TEXT,                        -- Internet Archive download URL
    archive_today_url TEXT,             -- archive.today snapshot URL

    -- Status tracking
    wikimedia_status TEXT,              -- 'done', 'failed', 'in-progress' (from Wikimedia)
    our_status TEXT DEFAULT 'pending',  -- 'pending', 'downloading', 'downloaded',
                                        -- 'uploading', 'uploaded', 'included', 'failed'

    -- Timestamps
    wikimedia_date TIMESTAMP,           -- When Wikimedia completed the dump
    discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    downloaded_at TIMESTAMP,
    uploaded_at TIMESTAMP,

    -- Error tracking
    error_message TEXT,                 -- Last error if status is 'failed'

    UNIQUE(wiki_db_name, cycle_date, filename)
);

-- Indexes for common queries
CREATE INDEX idx_dumps_cycle ON dumps(cycle_date);
CREATE INDEX idx_dumps_wiki ON dumps(wiki_db_name, cycle_date);
CREATE INDEX idx_dumps_status ON dumps(our_status);
CREATE INDEX idx_dumps_project_lang ON dumps(project, language);
CREATE INDEX idx_dumps_type ON dumps(dump_type);
```

**Status Values**:

**wikimedia_status**:
- `done`: Wikimedia successfully completed the dump
- `failed`: Wikimedia dump failed on their side
- `in-progress`: Wikimedia still generating the dump
- `null`: Unknown/not yet scraped

**our_status**:
- `pending`: Discovered but not yet downloaded
- `downloading`: Download in progress
- `downloaded`: Downloaded and checksum verified
- `uploading`: Uploading to Internet Archive
- `uploaded`: Successfully uploaded to IA
- `included`: Included in torrent
- `failed`: Processing failed (see error_message)

**Example Data**:
```sql
INSERT INTO dumps (
    project, language, wiki_db_name, cycle_date, dump_type, filename,
    is_history, size_bytes, md5, sha1,
    wikimedia_url, wikimedia_status, our_status
) VALUES (
    'wikipedia', 'en', 'enwiki', '2026-01-20', 'pages-articles',
    'enwiki-20260120-pages-articles1.xml.bz2',
    0, 15728640, 'abc123...', 'def456...',
    'https://dumps.wikimedia.org/enwiki/20260120/enwiki-20260120-pages-articles1.xml.bz2',
    'done', 'pending'
);
```

---

### 3. jobs

Job queue table with state machine tracking.

```sql
CREATE TABLE jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Job identification
    job_type TEXT NOT NULL,             -- 'discover_wikis', 'download_dump', 'upload_ia',
                                        -- 'create_torrent', 'publish_manifest'

    -- Status and state
    status TEXT DEFAULT 'pending',      -- 'pending', 'in_progress', 'completed', 'failed'

    -- Relationships
    parent_job_id INTEGER,              -- Parent job that must complete first
    dump_id INTEGER,                    -- Related dump (for download/upload jobs)
    cycle_date DATE,                    -- Which cycle this job belongs to

    -- Job parameters and results
    params TEXT,                        -- JSON: job-specific parameters
    result TEXT,                        -- JSON: job results (e.g., IA identifier)

    -- Retry logic
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 5,
    next_retry_at TIMESTAMP,
    last_error TEXT,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,

    -- Logging
    logs_path TEXT,                     -- Path to detailed logs for this job

    FOREIGN KEY (parent_job_id) REFERENCES jobs(id) ON DELETE SET NULL,
    FOREIGN KEY (dump_id) REFERENCES dumps(id) ON DELETE SET NULL
);

-- Indexes for job polling and queries
CREATE INDEX idx_jobs_type_status ON jobs(job_type, status);
CREATE INDEX idx_jobs_parent ON jobs(parent_job_id);
CREATE INDEX idx_jobs_dump ON jobs(dump_id);
CREATE INDEX idx_jobs_cycle ON jobs(cycle_date);
CREATE INDEX idx_jobs_created ON jobs(created_at);
CREATE INDEX idx_jobs_next_retry ON jobs(next_retry_at) WHERE status = 'pending' AND next_retry_at IS NOT NULL;
```

**Job Types**:
- `discover_wikis`: Scrape Wikimedia for available dumps, create dump records
- `download_dump`: Download a specific dump file
- `upload_ia`: Upload a dump to Internet Archive
- `create_torrent`: Bundle dumps into torrent(s) for a cycle
- `publish_manifest`: Publish manifest and torrents to R2/Gist/pastebin

**Status Values**:
- `pending`: Ready to be picked up (or waiting for parent completion)
- `in_progress`: Currently being processed by a worker
- `completed`: Successfully finished
- `failed`: Failed after max_retries exceeded

**params JSON Examples**:

```json
// discover_wikis job
{
  "cycle_date": "2026-01-20",
  "include_history": true
}

// download_dump job
{
  "dump_id": 123,
  "url": "https://dumps.wikimedia.org/enwiki/20260120/enwiki-20260120-pages-articles.xml.bz2",
  "mirrors": ["https://mirror1.example.com/...", "https://mirror2.example.com/..."],
  "expected_md5": "abc123...",
  "expected_sha1": "def456..."
}

// upload_ia job
{
  "dump_id": 123,
  "local_path": "/data/dumps/enwiki/enwiki-20260120-pages-articles.xml.bz2",
  "ia_collection": "wikiseed",
  "ia_metadata": {
    "title": "enwiki Wikimedia Dump 2026-01-20",
    "mediatype": "data"
  }
}

// create_torrent job
{
  "cycle_date": "2026-01-20",
  "is_history": false,
  "include_uncompressed": true,
  "dump_ids": [123, 124, 125, ...]
}

// publish_manifest job
{
  "cycle_date": "2026-01-20",
  "torrent_ids": [1, 2, 3],
  "targets": ["r2", "gist", "pastebin"]
}
```

**result JSON Examples**:

```json
// download_dump result
{
  "local_path": "/data/dumps/enwiki/enwiki-20260120-pages-articles.xml.bz2",
  "size_bytes": 15728640,
  "download_duration_seconds": 120,
  "calculated_md5": "abc123...",
  "calculated_sha1": "def456...",
  "checksum_verified": true
}

// upload_ia result
{
  "ia_identifier": "wikiseed-enwiki-20260120",
  "ia_url": "https://archive.org/download/wikiseed-enwiki-20260120/enwiki-20260120-pages-articles.xml.bz2",
  "upload_duration_seconds": 300
}

// create_torrent result
{
  "torrent_file_path": "/data/torrents/wikimedia-dumps-2026-01-20.torrent",
  "info_hash": "abc123...",
  "total_size_bytes": 123456789,
  "file_count": 450,
  "piece_count": 7500
}

// publish_manifest result
{
  "r2_url": "https://r2.wikiseed.app/manifest.json",
  "gist_url": "https://gist.github.com/...",
  "pastebin_url": "https://pastebin.com/..."
}
```

**Example Data**:
```sql
-- Discovery job (no parent)
INSERT INTO jobs (job_type, status, cycle_date, params) VALUES (
    'discover_wikis',
    'pending',
    '2026-01-20',
    '{"cycle_date": "2026-01-20", "include_history": true}'
);

-- Download job (depends on discovery)
INSERT INTO jobs (job_type, status, parent_job_id, dump_id, cycle_date, params) VALUES (
    'download_dump',
    'pending',
    1,  -- parent is the discover_wikis job
    123,
    '2026-01-20',
    '{"dump_id": 123, "url": "https://...", "expected_md5": "abc123..."}'
);
```

---

### 4. torrents

Metadata for created torrents.

```sql
CREATE TABLE torrents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Torrent identification
    name TEXT NOT NULL,                 -- 'wikimedia-dumps-2026-01-20'
    filename TEXT NOT NULL,             -- 'wikimedia-dumps-2026-01-20.torrent'
    cycle_date DATE NOT NULL,

    -- Torrent type
    is_compressed BOOLEAN DEFAULT 1,    -- 1 for compressed, 0 for uncompressed
    is_history BOOLEAN DEFAULT 0,       -- 1 for full history torrent

    -- Torrent metadata
    info_hash TEXT NOT NULL UNIQUE,     -- BitTorrent info hash (hex)
    magnet_link TEXT NOT NULL,
    piece_size_bytes INTEGER,
    piece_count INTEGER,
    total_size_bytes INTEGER,
    file_count INTEGER,

    -- File locations
    torrent_file_path TEXT NOT NULL,    -- Local .torrent file path
    torrent_url TEXT,                   -- R2 URL for .torrent file download

    -- Trackers and webseeds
    trackers TEXT,                      -- JSON array of tracker URLs
    webseeds TEXT,                      -- JSON array of webseed URLs

    -- Publishing status
    published BOOLEAN DEFAULT 0,        -- 1 if published to R2/etc.
    published_at TIMESTAMP,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(cycle_date, is_compressed, is_history)
);

-- Indexes
CREATE INDEX idx_torrents_cycle ON torrents(cycle_date);
CREATE INDEX idx_torrents_published ON torrents(published);
CREATE INDEX idx_torrents_hash ON torrents(info_hash);
```

**Example Data**:
```sql
INSERT INTO torrents (
    name, filename, cycle_date, is_compressed, is_history,
    info_hash, magnet_link, total_size_bytes, file_count,
    torrent_file_path, trackers, webseeds
) VALUES (
    'wikimedia-dumps-2026-01-20',
    'wikimedia-dumps-2026-01-20.torrent',
    '2026-01-20',
    1, 0,
    'abc123def456...',
    'magnet:?xt=urn:btih:abc123def456...',
    123456789, 450,
    '/data/torrents/wikimedia-dumps-2026-01-20.torrent',
    '["udp://tracker.opentrackr.org:1337/announce", "udp://open.stealth.si:80/announce"]',
    '["https://archive.org/download/wikiseed-enwiki-20260120/enwiki-20260120-pages-articles.xml.bz2"]'
);
```

---

### 5. torrent_files

Many-to-many relationship between torrents and dump files.

```sql
CREATE TABLE torrent_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    torrent_id INTEGER NOT NULL,
    dump_id INTEGER NOT NULL,

    -- File path within torrent
    path_in_torrent TEXT NOT NULL,      -- 'compressed/en/wikipedia/enwiki-20260120-pages-articles.xml.bz2'

    -- File metadata (denormalized for torrent metadata generation)
    size_bytes INTEGER NOT NULL,

    FOREIGN KEY (torrent_id) REFERENCES torrents(id) ON DELETE CASCADE,
    FOREIGN KEY (dump_id) REFERENCES dumps(id) ON DELETE CASCADE,
    UNIQUE(torrent_id, dump_id)
);

-- Indexes
CREATE INDEX idx_torrent_files_torrent ON torrent_files(torrent_id);
CREATE INDEX idx_torrent_files_dump ON torrent_files(dump_id);
```

**Example Data**:
```sql
INSERT INTO torrent_files (torrent_id, dump_id, path_in_torrent, size_bytes) VALUES
    (1, 123, 'compressed/en/wikipedia/enwiki-20260120-pages-articles.xml.bz2', 15728640),
    (1, 124, 'compressed/fr/wikipedia/frwiki-20260120-pages-articles.xml.bz2', 8388608);
```

---

### 6. torrent_stats

Historical snapshot of torrent seeding statistics.

```sql
CREATE TABLE torrent_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    torrent_id INTEGER NOT NULL,

    -- Seeding statistics
    seeders INTEGER DEFAULT 0,
    leechers INTEGER DEFAULT 0,
    completed INTEGER DEFAULT 0,        -- Total downloads completed (from tracker)

    -- Source of stats
    source TEXT,                        -- 'tracker', 'qbittorrent', 'manual'

    -- Timestamp
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (torrent_id) REFERENCES torrents(id) ON DELETE CASCADE
);

-- Indexes
CREATE INDEX idx_torrent_stats_torrent ON torrent_stats(torrent_id, recorded_at DESC);
CREATE INDEX idx_torrent_stats_recorded ON torrent_stats(recorded_at);
```

**Purpose**:
- Track seeding health over time
- Generate graphs of seeders/leechers
- Identify torrents that need more seeders
- Show download counts on web UI

**Data Collection**:
- Controller periodically scrapes tracker or qBittorrent API
- Stores snapshot every 6-24 hours
- Old stats retained for historical analysis

**Example Data**:
```sql
INSERT INTO torrent_stats (torrent_id, seeders, leechers, completed, source) VALUES
    (1, 15, 3, 127, 'tracker'),
    (2, 8, 1, 45, 'tracker');
```

---

## Database Initialization

### Initial Setup Script

```sql
-- migrations/001_initial.sql

-- Enable foreign keys and configure SQLite
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;

-- Create tables in dependency order
CREATE TABLE IF NOT EXISTS system_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_system_state_updated ON system_state(updated_at);

-- Insert initial system state
INSERT OR IGNORE INTO system_state (key, value) VALUES
    ('schema_version', '1'),
    ('system_health', 'initializing');

-- [Rest of table creation statements from above...]

-- Update system state
UPDATE system_state SET value = 'healthy' WHERE key = 'system_health';
```

### Python Initialization Script

```python
# scripts/init_db.py

import sqlite3
from pathlib import Path

DB_PATH = Path("/data/db/jobs.db")
MIGRATIONS_DIR = Path(__file__).parent.parent / "migrations"

def init_database():
    """Initialize database with latest schema."""

    # Create database directory if needed
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Connect to database
    conn = sqlite3.connect(DB_PATH)

    # Configure SQLite
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")

    # Get current schema version
    try:
        cursor = conn.execute("SELECT value FROM system_state WHERE key = 'schema_version'")
        current_version = int(cursor.fetchone()[0])
    except (sqlite3.OperationalError, TypeError):
        current_version = 0

    # Run migrations
    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    for migration_file in migration_files:
        # Extract version from filename (e.g., 001_initial.sql -> 1)
        version = int(migration_file.stem.split('_')[0])

        if version > current_version:
            print(f"Applying migration {migration_file.name}...")
            with open(migration_file) as f:
                conn.executescript(f.read())
            print(f"✓ Migration {version} applied")

    conn.commit()
    conn.close()
    print(f"Database initialized at {DB_PATH}")

if __name__ == "__main__":
    init_database()
```

---

## Database Migrations

### Migration Strategy

WikiSeed uses **numbered SQL migration scripts** for schema changes:

```
migrations/
├── 001_initial.sql           # Initial schema
├── 002_add_stats.sql          # Add torrent_stats table (future)
└── 003_add_indices.sql        # Add performance indexes (future)
```

### Creating a New Migration

1. **Create migration file**: `migrations/00N_description.sql`
2. **Write migration SQL**: Include CREATE, ALTER, INSERT as needed
3. **Update schema_version**: Migration should update `system_state` version
4. **Test migration**: Run against copy of production database
5. **Deploy**: Include migration in next release

**Example Migration** (adding a new table):

```sql
-- migrations/002_add_metrics.sql

-- Add metrics table for performance tracking
CREATE TABLE IF NOT EXISTS metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    metric_name TEXT NOT NULL,
    metric_value REAL NOT NULL,
    cycle_date DATE,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_metrics_name ON metrics(metric_name, recorded_at);

-- Update schema version
UPDATE system_state SET value = '2', updated_at = CURRENT_TIMESTAMP
WHERE key = 'schema_version';
```

### Applying Migrations

**Manual Application**:
```bash
# Apply specific migration
sqlite3 /data/db/jobs.db < migrations/002_add_metrics.sql
```

**Automatic on Startup**:
```python
# In controller container startup
from scripts.init_db import init_database
init_database()  # Applies all pending migrations
```

---

## Common Queries

### Check System Status

```sql
SELECT * FROM system_state;
```

### Get Current Cycle Progress

```sql
SELECT
    job_type,
    status,
    COUNT(*) as count
FROM jobs
WHERE cycle_date = '2026-01-20'
GROUP BY job_type, status
ORDER BY job_type, status;
```

### Find Failed Jobs

```sql
SELECT
    id,
    job_type,
    cycle_date,
    retry_count,
    last_error,
    created_at
FROM jobs
WHERE status = 'failed'
ORDER BY created_at DESC
LIMIT 20;
```

### Get Dumps for Current Cycle

```sql
SELECT
    project,
    language,
    dump_type,
    our_status,
    size_bytes / 1024 / 1024 as size_mb,
    filename
FROM dumps
WHERE cycle_date = (SELECT value FROM system_state WHERE key = 'current_cycle_date')
ORDER BY project, language, dump_type;
```

### Check Dump Download Progress

```sql
SELECT
    our_status,
    COUNT(*) as count,
    SUM(size_bytes) / 1024 / 1024 / 1024 as total_gb
FROM dumps
WHERE cycle_date = '2026-01-20'
GROUP BY our_status;
```

### Find Jobs Ready to Run

```sql
-- Jobs ready for processing (no parent or parent completed)
SELECT
    id,
    job_type,
    cycle_date,
    created_at
FROM jobs
WHERE status = 'pending'
  AND job_type = 'download_dump'
  AND (parent_job_id IS NULL
       OR EXISTS (SELECT 1 FROM jobs p
                  WHERE p.id = jobs.parent_job_id
                  AND p.status = 'completed'))
  AND (next_retry_at IS NULL OR next_retry_at <= CURRENT_TIMESTAMP)
ORDER BY created_at ASC
LIMIT 10;
```

### Get Torrent Statistics

```sql
-- Latest stats for all torrents
SELECT
    t.name,
    t.cycle_date,
    ts.seeders,
    ts.leechers,
    ts.completed,
    ts.recorded_at
FROM torrents t
LEFT JOIN torrent_stats ts ON t.id = ts.torrent_id
WHERE ts.id IN (
    SELECT MAX(id)
    FROM torrent_stats
    GROUP BY torrent_id
)
ORDER BY t.cycle_date DESC;
```

### Get Manifest Data

```sql
-- All data needed for manifest.json generation
SELECT
    t.name as torrent_name,
    t.magnet_link,
    t.torrent_url,
    t.cycle_date,
    t.total_size_bytes,
    d.project,
    d.language,
    d.dump_type,
    d.filename,
    d.size_bytes,
    d.md5,
    d.sha1,
    d.sha256,
    d.wikimedia_url,
    d.ia_url,
    tf.path_in_torrent
FROM torrents t
JOIN torrent_files tf ON t.id = tf.torrent_id
JOIN dumps d ON tf.dump_id = d.id
WHERE t.published = 1
ORDER BY t.cycle_date DESC, d.project, d.language, d.dump_type;
```

### Cycle Completion Check

```sql
-- Check if all downloads complete for cycle
SELECT
    COUNT(*) as pending_downloads
FROM jobs
WHERE cycle_date = '2026-01-20'
  AND job_type = 'download_dump'
  AND status != 'completed';

-- If result is 0, all downloads done, ready for torrent creation
```

---

## Performance Optimization

### Critical Indexes

All indexes listed in table schemas above are critical for performance. Key indexes:

```sql
-- Job polling queries
CREATE INDEX idx_jobs_type_status ON jobs(job_type, status);
CREATE INDEX idx_jobs_parent ON jobs(parent_job_id);

-- Dump status queries
CREATE INDEX idx_dumps_cycle ON dumps(cycle_date);
CREATE INDEX idx_dumps_status ON dumps(our_status);

-- Torrent file lookups
CREATE INDEX idx_torrent_files_torrent ON torrent_files(torrent_id);
```

### Query Performance Tips

1. **Use EXPLAIN QUERY PLAN** to verify index usage
2. **Filter early**: Add WHERE clauses before JOINs when possible
3. **Limit results**: Always use LIMIT for large result sets
4. **Avoid SELECT ***: Only select needed columns
5. **Use covering indexes**: Include commonly selected columns in index

### SQLite Vacuum

Periodically vacuum database to reclaim space and optimize:

```bash
# Monthly maintenance
sqlite3 /data/db/jobs.db "VACUUM;"
```

---

## Backup and Recovery

### Backup Strategy

**Automated Daily Backup** (cron at 2 AM UTC):

```bash
#!/bin/bash
# backup_db.sh

BACKUP_DIR=/backups/wikiseed/db
DATE=$(date +%Y-%m-%d)
DB_PATH=/data/db/jobs.db

# Create backup using SQLite backup API
sqlite3 $DB_PATH ".backup ${BACKUP_DIR}/jobs-${DATE}.db"

# Compress backup
gzip ${BACKUP_DIR}/jobs-${DATE}.db

# Retention: Keep 7 daily, 4 weekly, 12 monthly
# Delete backups older than 7 days (except weekly on Sundays)
find ${BACKUP_DIR} -name "jobs-*.db.gz" -mtime +7 \
    ! -name "jobs-*-01.db.gz" \
    ! -name "jobs-*-08.db.gz" \
    ! -name "jobs-*-15.db.gz" \
    ! -name "jobs-*-22.db.gz" \
    ! -name "jobs-*-29.db.gz" \
    -delete

echo "Backup completed: jobs-${DATE}.db.gz"
```

### Restore Procedure

```bash
# Stop all containers
docker-compose down

# Restore database from backup
gunzip -c /backups/wikiseed/db/jobs-2026-01-18.db.gz > /data/db/jobs.db

# Restart containers
docker-compose up -d

# Verify restoration
docker-compose exec controller sqlite3 /data/db/jobs.db "SELECT value FROM system_state WHERE key = 'schema_version';"
```

### Recovery Point Objective (RPO)

- **RPO**: 24 hours (daily backups)
- **RTO**: 4 hours (time to restore and verify)

### Disaster Recovery

1. **Database corruption**: Restore from most recent backup
2. **Accidental deletion**: Restore specific records from backup
3. **Failed migration**: Restore pre-migration backup, fix migration script
4. **Data loss**: WAL mode minimizes risk; backups provide recovery

---

## Data Retention

### Active Data
- **All jobs**: Retained indefinitely for historical analysis
- **All dumps**: Retained indefinitely
- **Torrent stats**: Retained indefinitely (grows slowly)

### Archival Strategy

If database grows too large (>10GB), consider:

1. **Export old cycles** to JSON/CSV for cold storage
2. **Delete jobs older than 2 years** (keep dumps table)
3. **Aggregate torrent_stats** to daily summaries after 1 year

**Example Archival Query**:
```sql
-- Archive jobs older than 2 years
DELETE FROM jobs
WHERE created_at < DATE('now', '-2 years')
  AND status IN ('completed', 'failed');
```

---

## Database Monitoring

### Health Checks

```sql
-- Check database integrity
PRAGMA integrity_check;

-- Check foreign key violations
PRAGMA foreign_key_check;

-- Database size
SELECT page_count * page_size / 1024 / 1024 as size_mb
FROM pragma_page_count(), pragma_page_size();

-- Table sizes
SELECT
    name,
    SUM("pgsize") / 1024 / 1024 as size_mb
FROM "dbstat"
GROUP BY name
ORDER BY size_mb DESC;
```

### Metrics to Track

- **Database size**: Alert if >5GB (expected max ~2GB)
- **Job queue depth**: Alert if >1000 pending jobs
- **Failed job count**: Alert if >10 failed jobs in current cycle
- **Long-running jobs**: Alert if job in_progress >24 hours

---

## Security

### File Permissions

```bash
# Set restrictive permissions on database
chmod 600 /data/db/jobs.db
chown 1000:1000 /data/db/jobs.db
```

### SQL Injection Prevention

Always use parameterized queries:

```python
# ✓ GOOD: Parameterized query
cursor.execute("SELECT * FROM jobs WHERE job_type = ?", (job_type,))

# ✗ BAD: String interpolation (SQL injection risk)
cursor.execute(f"SELECT * FROM jobs WHERE job_type = '{job_type}'")
```

### Access Control

- Database file only accessible to WikiSeed containers (bind mount permissions)
- No remote database access (SQLite is local file)
- Monitor web UI has read-only access

---

## Related Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md): Container architecture and job queue design
- [DEPLOYMENT.md](DEPLOYMENT.md): Production deployment and backup procedures
- [DEVELOPMENT.md](DEVELOPMENT.md): Development environment and testing
