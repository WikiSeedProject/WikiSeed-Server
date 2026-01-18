# WikiSeed: Technical Architecture

## Overview

WikiSeed uses a containerized microservices architecture coordinated through a job queue system. This document describes the technical implementation details for the server-side components.

## Technology Stack

### Core Technologies
- **Python**: 3.12+ (type hints, modern syntax, tomllib for config)
- **Database**: SQLite (single-file, simple deployment, no separate DB server)
- **Orchestration**: Docker Compose (single-host deployment)
- **Torrent Client**: qBittorrent or Transmission (official container images)
- **Web Framework**: Flask or FastAPI (for monitoring UI)

### Key Dependencies
- **SQLite3**: Python built-in, no additional install
- **requests**: HTTP client for API calls
- **schedule** or **APScheduler**: Internal job scheduling in controller
- **qbittorrent-api** or **transmission-rpc**: Torrent client integration
- **py7zr** or **zipfile**: Archive handling for decompression

### Development Tools
- **black**: Code formatter
- **ruff**: Fast linter and import sorter
- **mypy**: Type checker
- **pytest**: Testing framework
- **pre-commit**: Git hooks for code quality

## Container Architecture

### Container Overview

WikiSeed runs **7 containers** in a single Docker Compose environment:

1. **Controller**: Schedules jobs, monitors system health
2. **Scraper**: Discovers dumps from Wikimedia, archives to archive.today
3. **Downloader**: Downloads dump files from Wikimedia
4. **Uploader**: Uploads dumps to Internet Archive
5. **Creator**: Creates torrents and metadata files
6. **Publisher**: Publishes to R2, Gist, pastebin
7. **Seeder**: qBittorrent/Transmission for torrent seeding
8. **Monitor**: Web UI for status and logs (optional)

### Container Interaction Diagram

```
┌─────────────┐     ┌──────────────┐
│ Controller  │────▶│   SQLite DB  │
│ (schedules) │     │  (jobs.db)   │
└─────────────┘     └──────────────┘
                           │
       ┌───────────────────┼───────────────────┐
       │                   │                   │
       ▼                   ▼                   ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Scraper    │     │ Downloader  │     │  Uploader   │
│ (discovers) │     │ (fetches)   │     │ (to IA)     │
└─────────────┘     └─────────────┘     └─────────────┘
                           │                   │
                           └─────────┬─────────┘
                                     ▼
                              ┌─────────────┐
                              │  Creator    │
                              │ (torrents)  │
                              └─────────────┘
                                     │
                      ┌──────────────┼──────────────┐
                      ▼              ▼              ▼
               ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
               │ Publisher   │ │   Seeder    │ │  Monitor    │
               │ (R2, Gist)  │ │(qBittorrent)│ │  (web UI)   │
               └─────────────┘ └─────────────┘ └─────────────┘
```

### Container Specifications

#### 1. Controller

**Responsibility**: Central orchestration and job scheduling

**Behavior**:
- Runs continuously (24/7)
- Uses `schedule` library for cycle scheduling
- Creates jobs at configured times (1st and 20th of month)
- Monitors job progress and system health
- Sends email alerts on failures

**Job Creation Logic**:
```python
# Pseudocode
def schedule_cycle():
    # Create discover job
    create_job(type='discover_wikis', cycle_date='2026-01-20')

    # Wait for discovery to complete
    # Then create download jobs (one per dump file)
    for dump in discovered_dumps:
        create_job(type='download_dump', dump_id=dump.id, parent_job_id=discover_job.id)
```

**Configuration**:
- Poll interval: 60s (check for completed jobs, update status)
- Email alerts: SMTP config in environment
- Logging: stdout (captured by Docker)

**Dockerfile**:
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY controller/ .
CMD ["python", "controller.py"]
```

---

#### 2. Scraper

**Responsibility**: Discover available dumps and archive dump pages

**Behavior**:
- Polls database every 30s for `discover_wikis` jobs
- Queries Wikimedia dump API for available dumps
- Stores dump metadata in `dumps` table
- Archives dump index pages to archive.today
- Creates child `download_dump` jobs for each discovered dump

**Wikimedia API Interaction**:
```python
# Query dumpstatus.json for each wiki
url = f"https://dumps.wikimedia.org/{wiki}/dumpstatus.json"
response = requests.get(url)
dump_data = response.json()

# Extract dump files and metadata
for job_name, job_data in dump_data['jobs'].items():
    if job_data['status'] == 'done':
        # Store in dumps table
        # Create download job
```

**archive.today Integration**:
- Submits dump index URL to archive.today API during discovery
- Stores archive URL in `dumps.archive_url` field
- Retries on API rate limits (exponential backoff)

**Configuration**:
- Poll interval: 30s
- Wikimedia API rate limit: 100 req/min (respectful crawling)
- archive.today API: Submit save request, poll for completion

---

#### 3. Downloader

**Responsibility**: Download dump files from Wikimedia mirrors

**Behavior**:
- Polls database every 30s for `download_dump` jobs
- Downloads files using HTTP range requests (resumable)
- Verifies MD5/SHA1 checksums from Wikimedia
- Marks job complete or failed after retries

**Download Strategy**:
```python
# Chunk-based resumable downloads
chunk_size = 100 * 1024 * 1024  # 100 MB chunks
headers = {'Range': f'bytes={start}-{end}'}

# Verify checksums after download
calculated_md5 = hashlib.md5(file_data).hexdigest()
if calculated_md5 != expected_md5:
    raise ChecksumError()
```

**Retry Logic**:
- Attempt 1: Immediate
- Attempt 2: +5 minutes
- Attempt 3: +15 minutes
- Attempt 4: +1 hour
- Attempt 5: +4 hours
- After 5 failures: Mark `status='failed'`

**Configuration**:
- Poll interval: 30s
- Download directory: `/data/dumps/` (bind mount)
- Parallel downloads: 1 per container (single container instance)
- Bandwidth limit: Configurable (default: unlimited)

---

#### 4. Uploader

**Responsibility**: Upload dumps to Internet Archive

**Behavior**:
- Polls database every 30s for `upload_ia` jobs
- Uses Internet Archive API to create items and upload files
- Stores IA identifiers and URLs in `dumps.ia_identifier` and `dumps.ia_url`
- Creates child jobs for torrent creation once uploads complete

**IA Upload Flow**:
```python
import internetarchive as ia

# Create IA item
item = ia.get_item(identifier)
item.upload(
    files=[dump_file_path],
    metadata={
        'title': f'{wiki} Wikimedia Dump {cycle_date}',
        'collection': 'wikiseed',
        'mediatype': 'data',
        'subject': ['wikimedia', 'wikipedia', 'dumps'],
    }
)

# Store IA URL for webseed
ia_url = f"https://archive.org/download/{identifier}/{filename}"
```

**Configuration**:
- Poll interval: 30s
- IA credentials: Environment variables (`IA_ACCESS`, `IA_SECRET`)
- Upload retries: Same exponential backoff as downloader

---

#### 5. Creator

**Responsibility**: Create torrents with metadata and webseeds

**Behavior**:
- Polls database every 30s for `create_torrent` jobs
- Bundles all dumps for a cycle into torrent directory structure
- Generates metadata files (HASH.json, STATUS.json, README.txt, etc.)
- Creates .torrent files with webseeds (IA URLs, Wikimedia mirrors)
- Drops .torrent files into seeder watch directory

**Torrent Creation Flow**:
```python
# Build torrent directory structure
torrent_root = f"/data/torrents/wikimedia-dumps-{cycle_date}/"
create_directory_structure(torrent_root)

# Copy/hardlink dump files
for dump in cycle_dumps:
    dest = f"{torrent_root}/compressed/{dump.language}/{dump.project}/{dump.filename}"
    os.link(dump.download_path, dest)  # Hard link to save space

# Generate metadata files
generate_hash_file(torrent_root)
generate_status_file(torrent_root)
generate_readme(torrent_root)

# Create .torrent file
import torf
torrent = torf.Torrent(
    path=torrent_root,
    trackers=PUBLIC_TRACKERS,
    webseeds=[dump.ia_url for dump in cycle_dumps],
    private=False,
)
torrent.generate()
torrent.write(f"/data/torrents/{cycle_date}.torrent")
```

**Metadata Files Generated**:
- `HASH.json` / `HASH.txt`: MD5, SHA1 (Wikimedia), SHA256 (generated)
- `STATUS.json` / `STATUS.txt`: Per-dump success/failure status
- `ARCHIVE_URLS.json` / `ARCHIVE_URLS.txt`: archive.today links
- `README.txt`: Format explanations, usage instructions
- `LICENSE.txt`: WikiSeed and content licenses
- `VERSION.txt`: Version of docs/tools included

**Configuration**:
- Poll interval: 30s
- Torrent output directory: `/data/torrents/`
- Seeder watch directory: `/data/seeder/watch/`
- Public trackers: List from https://torrends.to/torrent-tracker-list/

---

#### 6. Publisher

**Responsibility**: Publish manifest and torrents to distribution channels

**Behavior**:
- Polls database every 30s for `publish_manifest` jobs
- Generates manifest.json and manifest.txt
- Uploads to Cloudflare R2, GitHub Gist, pastebin.com
- Uploads .torrent files to R2
- Optionally uploads to Academic Torrents

**Manifest Generation**:
```python
manifest = {
    "version": "1.0",
    "last_updated": datetime.utcnow().isoformat(),
    "torrents": [
        {
            "name": "wikimedia-dumps-2026-01-20.torrent",
            "magnet": "magnet:?xt=urn:btih:...",
            "url": "https://r2.wikiseed.app/torrents/2026-01-20.torrent",
            "cycle_date": "2026-01-20",
            "size_bytes": 123456789,
            "files": [
                {
                    "project": "wikipedia",
                    "language": "en",
                    "filename": "...",
                    "size_bytes": 12345,
                    "md5": "...",
                    "sha1": "...",
                    "sha256": "...",
                    "ia_url": "https://archive.org/download/...",
                }
            ]
        }
    ]
}
```

**Distribution Channels**:
- **Cloudflare R2**: Primary storage for .torrent files and manifest
- **GitHub Gist**: Manifest.json backup
- **pastebin.com**: Manifest.txt backup
- **Academic Torrents**: Auto-upload via API (optional)

**Configuration**:
- Poll interval: 30s
- R2 credentials: Environment variables
- Gist token: Environment variable
- pastebin API key: Environment variable

---

#### 7. Seeder

**Responsibility**: Seed torrents to the swarm

**Behavior**:
- Runs qBittorrent or Transmission container
- Watches `/data/seeder/watch/` directory for new .torrent files
- Automatically adds and starts seeding new torrents
- No custom code required (off-the-shelf client)

**Docker Compose Configuration**:
```yaml
seeder:
  image: linuxserver/qbittorrent:latest
  container_name: wikiseed-seeder
  environment:
    - PUID=1000
    - PGID=1000
    - TZ=UTC
    - WEBUI_PORT=8080
  volumes:
    - /path/to/seeder/config:/config
    - /path/to/seeder/watch:/watch
    - /path/to/torrents:/data/torrents:ro  # Read-only access to torrent data
  ports:
    - "8080:8080"  # WebUI
    - "6881:6881"  # BitTorrent
    - "6881:6881/udp"
  restart: unless-stopped
```

**Configuration**:
- Watch directory: `/watch` (mapped to `/data/seeder/watch` on host)
- Data directory: `/data/torrents` (read-only, no copying needed)
- WebUI: http://localhost:8080
- Seeding limits: Unlimited (seed forever or until pruned)

---

#### 8. Monitor (Optional)

**Responsibility**: Web UI for monitoring system status

**Behavior**:
- Lightweight Flask/FastAPI app
- Read-only access to SQLite database
- Displays job status, recent logs, system health
- No authentication (bind to localhost) or basic auth

**Dashboard Views**:
- **Overview**: Current cycle progress, active jobs, failures
- **Jobs**: Filterable table of all jobs with status
- **Logs**: Recent container logs (via Docker API)
- **Stats**: Processing time, sizes, success rates

**Configuration**:
- Port: 8000 (bind to localhost or with basic auth)
- Database: Read-only connection to `/data/db/jobs.db`
- Refresh interval: 10s (auto-refresh)

---

## Data Flow

### Directory Structure

```
/path/to/wikiseed/
├── data/
│   ├── db/
│   │   └── jobs.db              # SQLite database
│   ├── dumps/                   # Downloaded dump files
│   │   ├── enwiki/
│   │   ├── frwiki/
│   │   └── ...
│   ├── torrents/                # Created torrents
│   │   ├── wikimedia-dumps-2026-01-20/
│   │   │   ├── compressed/
│   │   │   ├── uncompressed/
│   │   │   ├── README.txt
│   │   │   ├── HASH.json
│   │   │   └── ...
│   │   └── ...
│   └── seeder/
│       └── watch/               # .torrent files for seeder
└── config/
    └── config.yaml              # System configuration
```

### Docker Compose Bind Mounts

```yaml
version: '3.8'

services:
  controller:
    volumes:
      - ./data/db:/data/db
      - ./config:/config:ro

  scraper:
    volumes:
      - ./data/db:/data/db
      - ./config:/config:ro

  downloader:
    volumes:
      - ./data/db:/data/db
      - ./data/dumps:/data/dumps
      - ./config:/config:ro

  uploader:
    volumes:
      - ./data/db:/data/db
      - ./data/dumps:/data/dumps:ro
      - ./config:/config:ro

  creator:
    volumes:
      - ./data/db:/data/db
      - ./data/dumps:/data/dumps:ro
      - ./data/torrents:/data/torrents
      - ./data/seeder/watch:/data/seeder/watch
      - ./config:/config:ro

  publisher:
    volumes:
      - ./data/db:/data/db
      - ./data/torrents:/data/torrents:ro
      - ./config:/config:ro

  seeder:
    volumes:
      - ./data/seeder/config:/config
      - ./data/seeder/watch:/watch
      - ./data/torrents:/data/torrents:ro

  monitor:
    volumes:
      - ./data/db:/data/db:ro
      - ./config:/config:ro
```

---

## Job Queue System

### Database Schema Overview

The job queue is implemented in SQLite with the following core tables:
- `wikis`: Wiki metadata (project, language)
- `dumps`: Dump file metadata
- `jobs`: Job queue with state machine
- `torrents`: Torrent metadata
- `torrent_files`: Many-to-many mapping of torrents to dump files

See [DATABASE.md](DATABASE.md) for complete schema details.

### Job State Machine

Jobs progress through the following states:

```
pending → in_progress → completed
                      ↘ failed (after retries)
```

**States**:
- `pending`: Job ready to be picked up by a worker
- `in_progress`: Worker actively processing
- `completed`: Job finished successfully
- `failed`: Job failed after all retries exhausted

### Job Polling Logic

Each worker container polls for jobs every 30 seconds:

```python
import sqlite3
import time

def poll_for_jobs(job_type):
    while True:
        conn = sqlite3.connect('/data/db/jobs.db', timeout=30)
        conn.execute('BEGIN IMMEDIATE')  # Acquire write lock

        cursor = conn.execute("""
            SELECT id, dump_id, parent_job_id, params
            FROM jobs
            WHERE job_type = ?
              AND status = 'pending'
              AND (parent_job_id IS NULL
                   OR EXISTS (SELECT 1 FROM jobs p
                              WHERE p.id = jobs.parent_job_id
                              AND p.status = 'completed'))
            ORDER BY created_at ASC
            LIMIT 1
        """, (job_type,))

        job = cursor.fetchone()

        if job:
            # Mark job as in_progress
            conn.execute("""
                UPDATE jobs
                SET status = 'in_progress',
                    started_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (job[0],))
            conn.commit()

            # Process job
            try:
                process_job(job)
                mark_complete(job[0])
            except Exception as e:
                handle_failure(job[0], e)

        conn.close()
        time.sleep(30)  # Poll every 30s
```

### Race Condition Prevention

**Problem**: Multiple workers might try to claim the same job.

**Solution**: SQLite's `BEGIN IMMEDIATE` acquires a write lock before reading, preventing other connections from starting their own transactions. This ensures only one worker can claim a job.

```python
# Worker 1 and Worker 2 both try to get a job
# Worker 1's BEGIN IMMEDIATE succeeds first
# Worker 2's BEGIN IMMEDIATE blocks until Worker 1 commits
# Worker 2 then sees the job is already in_progress and skips it
```

### Job Dependencies

Jobs use `parent_job_id` for dependencies:

```python
# Discovery job (no parent)
discover_job = create_job(
    job_type='discover_wikis',
    cycle_date='2026-01-20',
    parent_job_id=None,
)

# Download jobs depend on discovery
for dump in discovered_dumps:
    download_job = create_job(
        job_type='download_dump',
        dump_id=dump.id,
        parent_job_id=discover_job.id,  # Won't start until discovery completes
    )

# Torrent creation depends on all downloads
# Controller checks all downloads completed before creating this job
torrent_job = create_job(
    job_type='create_torrent',
    cycle_date='2026-01-20',
    parent_job_id=None,  # No single parent, controller ensures all downloads done
)
```

### Job Types and Flow

1. **discover_wikis**: Scraper queries Wikimedia, creates dump records and download jobs
2. **download_dump**: Downloader fetches file (parent: discover_wikis)
3. **upload_ia**: Uploader sends to IA (parent: download_dump)
4. **create_torrent**: Creator bundles cycle dumps (parent: all uploads complete)
5. **publish_manifest**: Publisher uploads to R2/Gist/pastebin (parent: create_torrent)

---

## Error Handling and Recovery

### Retry Strategy

Failed jobs retry with exponential backoff:

| Attempt | Delay      | Total Time Elapsed |
|---------|------------|--------------------|
| 1       | Immediate  | 0                  |
| 2       | +5 min     | 5 min              |
| 3       | +15 min    | 20 min             |
| 4       | +1 hour    | 1h 20min           |
| 5       | +4 hours   | 5h 20min           |

After 5 attempts, job is marked `failed` and alerts are sent.

### Retry Implementation

```python
def handle_failure(job_id, error):
    conn = sqlite3.connect('/data/db/jobs.db')

    # Increment retry count
    cursor = conn.execute("""
        UPDATE jobs
        SET retry_count = retry_count + 1,
            last_error = ?,
            status = CASE
                WHEN retry_count + 1 >= 5 THEN 'failed'
                ELSE 'pending'
            END,
            next_retry_at = CASE
                WHEN retry_count = 0 THEN DATETIME('now', '+5 minutes')
                WHEN retry_count = 1 THEN DATETIME('now', '+15 minutes')
                WHEN retry_count = 2 THEN DATETIME('now', '+1 hour')
                WHEN retry_count = 3 THEN DATETIME('now', '+4 hours')
                ELSE NULL
            END
        WHERE id = ?
    """, (str(error), job_id))

    conn.commit()
    conn.close()
```

### Failure Scenarios

#### Download Failure
- **Network timeout**: Retry with backoff
- **Checksum mismatch**: Re-download entire file
- **404 Not Found**: Mark failed immediately (dump not available)
- **Mirror failure**: Try different mirror from list

#### IA Upload Failure
- **Rate limited**: Retry with longer backoff
- **Authentication error**: Alert admin, halt pipeline
- **Quota exceeded**: Alert admin, skip upload but continue pipeline

#### Torrent Creation Failure
- **Missing dump files**: Skip missing files, document in STATUS.json
- **Disk full**: Alert admin, pause pipeline
- **Corruption detected**: Re-download affected dumps

### Monitoring and Alerts

**Email Alerts** (sent by controller):
- Job failed after all retries
- Critical errors (auth failures, disk full)
- Pipeline stalled (no progress for 6+ hours)

**Alert Configuration**:
```yaml
# config.yaml
alerts:
  email:
    enabled: true
    smtp_host: smtp.gmail.com
    smtp_port: 587
    from: alerts@wikiseed.app
    to: admin@example.com
    username: ${SMTP_USERNAME}
    password: ${SMTP_PASSWORD}
```

---

## Configuration Management

### Configuration File

Single `config.yaml` file mounted read-only into all containers:

```yaml
# config.yaml
wikiseed:
  version: "1.0"

  # Cycle scheduling
  scheduling:
    cycle_dates: [1, 20]  # Days of month to start cycles
    embargo_days: 1       # Process previous cycle while current generates
    publish_deadlines:
      first_cycle: 19     # Publish by 19th for 1st cycle
      second_cycle: -1    # Publish by last day of month for 20th cycle

  # Dump selection
  dumps:
    include_history: true  # Include full history dumps on 1st cycle
    regular_types:
      - pages-articles
      - pages-meta-current
      - abstract
      - all-titles
      - stub-articles
      - stub-meta-history
      - categorylinks
      - pagelinks
      - imagelinks
      - redirect
      - site_stats
    history_types:
      - pages-meta-history
      - abstract
      - all-titles
      - stub-meta-history

  # Download settings
  download:
    chunk_size_mb: 100
    max_retries: 5
    bandwidth_limit_mbps: 0  # 0 = unlimited
    wikimedia_mirrors:
      - https://dumps.wikimedia.org
      - https://dumps.wikimedia.your.org
      - https://mirror.accum.se/mirror/wikimedia.org

  # Storage management
  storage:
    dumps_path: /data/dumps
    torrents_path: /data/torrents
    max_storage_gb: 2000
    cleanup_threshold_pct: 85
    prune_oldest_first: true

  # Torrent creation
  torrents:
    trackers:
      - udp://tracker.opentrackr.org:1337/announce
      - udp://open.stealth.si:80/announce
      - udp://tracker.torrent.eu.org:451/announce
    webseeds_enabled: true
    piece_size_mb: 16

  # Internet Archive
  ia:
    collection: wikiseed
    metadata:
      mediatype: data
      subject: [wikimedia, wikipedia, dumps, archive]

  # Publishing
  publish:
    r2:
      enabled: true
      bucket: wikiseed-torrents
    gist:
      enabled: true
    pastebin:
      enabled: true
    academic_torrents:
      enabled: false  # Optional

  # Monitoring
  monitoring:
    web_ui_enabled: true
    web_ui_port: 8000
    log_retention_days: 90

  # Alerts
  alerts:
    email:
      enabled: true
      smtp_host: smtp.gmail.com
      smtp_port: 587
      from: alerts@wikiseed.app
      to: admin@example.com
```

### Environment Variables (Secrets)

Secrets stored in `.env` file (not committed to git):

```bash
# .env
# Internet Archive
IA_ACCESS=your_ia_access_key
IA_SECRET=your_ia_secret_key

# Cloudflare R2
R2_ACCOUNT_ID=your_account_id
R2_ACCESS_KEY_ID=your_access_key
R2_SECRET_ACCESS_KEY=your_secret_key

# GitHub Gist
GIST_TOKEN=your_github_token

# pastebin.com
PASTEBIN_API_KEY=your_pastebin_key

# archive.today
ARCHIVE_TODAY_API_KEY=your_archive_today_key  # If required

# Academic Torrents (optional)
ACADEMIC_TORRENTS_API_KEY=your_at_key

# SMTP (for alerts)
SMTP_USERNAME=your_smtp_user
SMTP_PASSWORD=your_smtp_password
```

### Docker Compose Secrets

```yaml
# docker-compose.yml
services:
  controller:
    env_file:
      - .env
    environment:
      - CONFIG_PATH=/config/config.yaml
```

---

## Development Workflow

### Local Development Setup

```bash
# Clone repository
git clone https://github.com/yourusername/wikiseed-server.git
cd wikiseed-server

# Create virtual environment
python3.12 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install

# Copy example config
cp config.example.yaml config.yaml
cp .env.example .env
# Edit .env with your credentials

# Initialize database
python scripts/init_db.py

# Run tests
pytest

# Start containers
docker-compose up -d
```

### Code Quality Standards

**Formatting**: `black` with default settings
```bash
black src/
```

**Linting**: `ruff` for fast linting and import sorting
```bash
ruff check src/
ruff check --fix src/  # Auto-fix
```

**Type Checking**: `mypy` with strict mode
```bash
mypy src/
```

**Pre-commit Hooks**:
```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/psf/black
    rev: 24.1.1
    hooks:
      - id: black

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.11
    hooks:
      - id: ruff
        args: [--fix]

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
```

### Testing Strategy

See [DEVELOPMENT.md](DEVELOPMENT.md) for complete testing details.

**Test Categories**:
- Unit tests: Test individual functions and classes
- Integration tests: Test container interactions and database
- End-to-end tests: Small wiki mode (full pipeline on tiny wikis)
- Dry run mode: Validate logic without downloads/uploads

---

## Deployment

### Production Deployment

```bash
# On production host
git clone https://github.com/yourusername/wikiseed-server.git
cd wikiseed-server

# Configure
cp config.example.yaml config.yaml
vim config.yaml  # Adjust paths, storage limits, etc.

cp .env.example .env
vim .env  # Add production credentials

# Create data directories
mkdir -p data/{db,dumps,torrents,seeder/{config,watch}}

# Initialize database
docker-compose run --rm controller python /app/init_db.py

# Start services
docker-compose up -d

# Verify
docker-compose ps
docker-compose logs -f controller
```

### Docker Compose Production Configuration

```yaml
# docker-compose.yml
version: '3.8'

services:
  controller:
    build: ./controller
    container_name: wikiseed-controller
    restart: unless-stopped
    volumes:
      - ./data/db:/data/db
      - ./config:/config:ro
    env_file:
      - .env
    environment:
      - CONFIG_PATH=/config/config.yaml
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  scraper:
    build: ./scraper
    container_name: wikiseed-scraper
    restart: unless-stopped
    volumes:
      - ./data/db:/data/db
      - ./config:/config:ro
    env_file:
      - .env
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  # ... similar for other containers

  seeder:
    image: linuxserver/qbittorrent:latest
    container_name: wikiseed-seeder
    restart: unless-stopped
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=UTC
      - WEBUI_PORT=8080
    volumes:
      - ./data/seeder/config:/config
      - ./data/seeder/watch:/watch
      - ./data/torrents:/data/torrents:ro
    ports:
      - "127.0.0.1:8080:8080"  # WebUI on localhost only
      - "6881:6881"
      - "6881:6881/udp"
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

### Backup Strategy

See [DEPLOYMENT.md](DEPLOYMENT.md) for complete backup procedures.

**Critical Data**:
- `/data/db/jobs.db`: SQLite database (daily backup)
- `/config/config.yaml`: Configuration (git tracked)
- `.env`: Secrets (secure backup, not in git)

**Backup Script** (cron daily at 2 AM):
```bash
#!/bin/bash
# backup.sh

BACKUP_DIR=/backups/wikiseed
DATE=$(date +%Y-%m-%d)

# Backup database
sqlite3 /path/to/data/db/jobs.db ".backup /tmp/jobs-${DATE}.db"
gzip /tmp/jobs-${DATE}.db
mv /tmp/jobs-${DATE}.db.gz ${BACKUP_DIR}/

# Retention: 7 daily, 4 weekly, 12 monthly
find ${BACKUP_DIR} -name "jobs-*.db.gz" -mtime +7 -delete
```

---

## Performance Considerations

### SQLite Optimizations

```sql
-- Indexes for job polling queries
CREATE INDEX idx_jobs_type_status ON jobs(job_type, status);
CREATE INDEX idx_jobs_parent ON jobs(parent_job_id);
CREATE INDEX idx_jobs_created ON jobs(created_at);

-- Pragma settings
PRAGMA journal_mode = WAL;  -- Write-Ahead Logging for better concurrency
PRAGMA synchronous = NORMAL;  -- Balance safety and performance
PRAGMA cache_size = 10000;  -- 10MB cache
PRAGMA temp_store = MEMORY;  -- Temp tables in RAM
```

### Container Resource Limits

```yaml
# docker-compose.yml
services:
  downloader:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
        reservations:
          cpus: '1.0'
          memory: 1G
```

### Scaling Considerations

**Single-Host Limits**:
- Current design: Single instance of each container
- Bottlenecks: Download bandwidth, disk I/O, IA upload rate
- Capacity: ~500 wikis per cycle with reasonable timing

**Future Scaling** (if needed):
- Multiple downloader containers (requires lock coordination)
- Multiple uploader containers
- Separate database server (PostgreSQL instead of SQLite)
- Multi-host deployment (Docker Swarm or Kubernetes)

---

## Security Considerations

### Secrets Management
- All credentials in `.env` file (not committed)
- `.env` file permissions: `chmod 600`
- Docker secrets preferred for production (future enhancement)
- Regular credential rotation (manual process)

### Container Isolation
- Containers run as non-root users (PUID/PGID)
- Read-only mounts where possible
- No privileged containers
- Network isolation (default bridge network)

### API Security
- Monitor web UI: localhost binding or basic auth
- No public-facing admin interfaces
- Rate limiting on external API calls (respectful crawling)

### Audit Trail
- All job state changes logged to database
- Container logs retained 90 days
- Failed job errors stored in jobs.last_error field

---

## Monitoring and Observability

### Logs

**Container Logs**:
```bash
# View all logs
docker-compose logs -f

# View specific container
docker-compose logs -f controller

# Last 100 lines
docker-compose logs --tail=100 downloader
```

**Log Retention**:
- Docker logs: 3 files × 10MB (rolling, configured in docker-compose.yml)
- Database: 90 days (configurable)

### Metrics

**Job Metrics** (stored in database):
- Jobs created, completed, failed per cycle
- Processing time per job type
- Download throughput (MB/s)
- IA upload success rate

**System Metrics** (via monitor UI):
- Disk usage (dumps, torrents, database)
- Container health (up/down, restart count)
- Active jobs and queue depth

### Health Checks

```yaml
# docker-compose.yml
services:
  controller:
    healthcheck:
      test: ["CMD", "python", "-c", "import sqlite3; sqlite3.connect('/data/db/jobs.db').execute('SELECT 1')"]
      interval: 60s
      timeout: 10s
      retries: 3
      start_period: 10s
```

---

## Future Enhancements

### Planned Improvements
- PostgreSQL support for multi-host deployments
- Multiple worker instances with improved locking
- Real-time dashboard with WebSocket updates
- Prometheus metrics export
- Grafana dashboards
- Automatic mirror health checking and selection
- RSS feed for new torrents
- Academic Torrents auto-submission
- Wikimedia bot for updating community pages

### Not Planned (Out of Scope)
- Wikimedia Commons media files
- Real-time dump monitoring (polling is sufficient)
- Custom torrent client (qBittorrent is excellent)

---

## Related Documentation

- [bigpicture.md](bigpicture.md): High-level strategy and mission
- [DATABASE.md](DATABASE.md): Complete database schema and migrations
- [DEPLOYMENT.md](DEPLOYMENT.md): Production deployment and operations
- [DEVELOPMENT.md](DEVELOPMENT.md): Development setup and testing
- [API.md](API.md): Monitor web UI and REST API reference
