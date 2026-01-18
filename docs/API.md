# WikiSeed: Monitor API Reference

## Overview

The WikiSeed Monitor provides a web-based interface and REST API for viewing system status, jobs, dumps, and torrents. This is a **read-only API** for monitoring purposes.

- **Framework**: Flask
- **Port**: 8000 (configurable)
- **Base URL**: `http://localhost:8000`
- **Authentication**: None (bind to localhost or use basic auth if exposed)
- **Response Format**: JSON for API endpoints, HTML for web UI

## Table of Contents

- [Web UI Pages](#web-ui-pages)
- [REST API Endpoints](#rest-api-endpoints)
- [Data Models](#data-models)
- [Error Handling](#error-handling)
- [Interactive Documentation](#interactive-documentation)

---

## Web UI Pages

The Monitor includes server-side rendered HTML pages for human consumption.

### Dashboard

**URL**: `/`

**Description**: Overview of system status and current cycle

**Features**:
- Current cycle date and progress
- Active jobs count by type and status
- Recent failures (last 10)
- System health indicators
- Disk usage
- Latest torrent statistics

**Example View**:
```
┌─────────────────────────────────────────────────┐
│ WikiSeed Monitor                                │
│                                                 │
│ Current Cycle: 2026-01-20                       │
│ System Health: Healthy ✓                        │
│ Disk Usage: 45% (900 GB / 2 TB)                 │
│                                                 │
│ Active Jobs:                                    │
│   discover_wikis    : ✓ Completed               │
│   download_dump     : 127/450 in progress       │
│   upload_ia         : 45/450 completed          │
│   create_torrent    : Pending                   │
│   publish_manifest  : Pending                   │
│                                                 │
│ Recent Failures: 2                              │
│   - download_dump #1234: Network timeout        │
│   - upload_ia #5678: Rate limited               │
└─────────────────────────────────────────────────┘
```

---

### Jobs Page

**URL**: `/jobs`

**Description**: Searchable, filterable table of all jobs

**Query Parameters**:
- `job_type`: Filter by job type (e.g., `download_dump`)
- `status`: Filter by status (e.g., `failed`)
- `cycle_date`: Filter by cycle (e.g., `2026-01-20`)
- `cursor`: Pagination cursor
- `limit`: Results per page (default: 100, max: 1000)

**Features**:
- Sort by created_at, started_at, completed_at
- Search by job ID
- View job details (params, result, error messages)
- Auto-refresh every 10 seconds

**Example Table**:
```
ID    Type            Status      Created              Started              Error
────────────────────────────────────────────────────────────────────────────────
1     discover_wikis  completed   2026-01-20 00:00:00  2026-01-20 00:00:05  -
2     download_dump   completed   2026-01-20 00:05:00  2026-01-20 00:05:10  -
3     download_dump   in_progress 2026-01-20 00:05:01  2026-01-20 00:06:00  -
4     download_dump   failed      2026-01-20 00:05:02  2026-01-20 00:05:30  Timeout
```

---

### Dumps Page

**URL**: `/dumps`

**Description**: List of all dump files with status

**Query Parameters**:
- `cycle_date`: Filter by cycle
- `project`: Filter by project (e.g., `wikipedia`)
- `language`: Filter by language (e.g., `en`)
- `our_status`: Filter by status (e.g., `downloaded`)
- `cursor`: Pagination cursor
- `limit`: Results per page (default: 100, max: 1000)

**Features**:
- Group by project and language
- Show download/upload progress
- Display file sizes and checksums
- Links to Wikimedia source and IA

**Example Table**:
```
Project    Lang  Type            Filename                        Status      Size
────────────────────────────────────────────────────────────────────────────────
wikipedia  en    pages-articles  enwiki-20260120-pages-art...    uploaded    2.5 GB
wikipedia  en    abstract        enwiki-20260120-abstract.xml    uploaded    150 MB
wikipedia  fr    pages-articles  frwiki-20260120-pages-art...    downloading 1.8 GB
```

---

### Torrents Page

**URL**: `/torrents`

**Description**: Published torrents with metadata and stats

**Query Parameters**:
- `cycle_date`: Filter by cycle
- `is_history`: Filter history torrents (true/false)

**Features**:
- Magnet links (click to copy)
- Download .torrent files
- Seeding statistics (seeders, leechers, completed)
- File count and total size
- Links to R2/Gist/pastebin

**Example Table**:
```
Name                          Cycle       Files  Size    Seeders  Leechers  Download
──────────────────────────────────────────────────────────────────────────────────────
wikimedia-dumps-2026-01-20    2026-01-20  450    850 GB  15       3         [.torrent]
wikimedia-dumps-2026-01-01    2026-01-01  450    820 GB  23       5         [.torrent]
```

---

## REST API Endpoints

All API endpoints return JSON responses.

### Base URL

```
http://localhost:8000/api/v1
```

### Endpoint Summary

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/health` | System health check |
| GET | `/api/v1/status` | Current system status |
| GET | `/api/v1/jobs` | List jobs |
| GET | `/api/v1/jobs/{id}` | Get job details |
| GET | `/api/v1/dumps` | List dumps |
| GET | `/api/v1/dumps/{id}` | Get dump details |
| GET | `/api/v1/torrents` | List torrents |
| GET | `/api/v1/torrents/{id}` | Get torrent details |
| GET | `/api/v1/stats/seeding` | Torrent seeding statistics |

---

### Health Check

**GET** `/api/v1/health`

Check if the Monitor API is running.

**Response**:
```json
{
  "status": "healthy",
  "timestamp": "2026-01-18T14:30:00Z",
  "version": "1.0.0"
}
```

**Status Codes**:
- `200 OK`: Service is healthy

---

### System Status

**GET** `/api/v1/status`

Get current system status and metrics.

**Response**:
```json
{
  "system_health": "healthy",
  "current_cycle_date": "2026-01-20",
  "schema_version": 1,
  "disk_usage": {
    "dumps_gb": 450,
    "torrents_gb": 50,
    "database_mb": 250,
    "total_gb": 500,
    "available_gb": 1500,
    "usage_percent": 25
  },
  "job_summary": {
    "pending": 323,
    "in_progress": 5,
    "completed": 127,
    "failed": 2
  },
  "dump_summary": {
    "pending": 300,
    "downloading": 20,
    "downloaded": 100,
    "uploading": 5,
    "uploaded": 80,
    "included": 50,
    "failed": 2
  },
  "last_publish_date": "2026-01-19",
  "uptime_seconds": 86400
}
```

**Status Codes**:
- `200 OK`: Success

---

### List Jobs

**GET** `/api/v1/jobs`

Get paginated list of jobs.

**Query Parameters**:
- `job_type` (string, optional): Filter by job type
  - Values: `discover_wikis`, `download_dump`, `upload_ia`, `create_torrent`, `publish_manifest`
- `status` (string, optional): Filter by status
  - Values: `pending`, `in_progress`, `completed`, `failed`
- `cycle_date` (string, optional): Filter by cycle date (YYYY-MM-DD)
- `cursor` (integer, optional): Job ID to start from (for pagination)
- `limit` (integer, optional): Results per page (default: 100, max: 1000)

**Response**:
```json
{
  "jobs": [
    {
      "id": 1,
      "job_type": "discover_wikis",
      "status": "completed",
      "cycle_date": "2026-01-20",
      "created_at": "2026-01-20T00:00:00Z",
      "started_at": "2026-01-20T00:00:05Z",
      "completed_at": "2026-01-20T00:02:30Z",
      "retry_count": 0,
      "last_error": null,
      "params": {
        "cycle_date": "2026-01-20",
        "include_history": true
      },
      "result": {
        "wikis_discovered": 450,
        "dumps_created": 3200
      }
    },
    {
      "id": 2,
      "job_type": "download_dump",
      "status": "in_progress",
      "cycle_date": "2026-01-20",
      "dump_id": 123,
      "parent_job_id": 1,
      "created_at": "2026-01-20T00:05:00Z",
      "started_at": "2026-01-20T00:05:10Z",
      "completed_at": null,
      "retry_count": 0,
      "last_error": null,
      "params": {
        "dump_id": 123,
        "url": "https://dumps.wikimedia.org/enwiki/...",
        "expected_md5": "abc123..."
      },
      "result": null
    }
  ],
  "pagination": {
    "cursor": 2,
    "limit": 100,
    "has_more": true,
    "next_cursor": 102
  }
}
```

**Status Codes**:
- `200 OK`: Success
- `400 Bad Request`: Invalid query parameters

---

### Get Job Details

**GET** `/api/v1/jobs/{id}`

Get detailed information about a specific job.

**Path Parameters**:
- `id` (integer): Job ID

**Response**:
```json
{
  "id": 2,
  "job_type": "download_dump",
  "status": "completed",
  "cycle_date": "2026-01-20",
  "dump_id": 123,
  "parent_job_id": 1,
  "created_at": "2026-01-20T00:05:00Z",
  "started_at": "2026-01-20T00:05:10Z",
  "completed_at": "2026-01-20T00:07:30Z",
  "retry_count": 1,
  "max_retries": 5,
  "next_retry_at": null,
  "last_error": "Network timeout (retried)",
  "params": {
    "dump_id": 123,
    "url": "https://dumps.wikimedia.org/enwiki/20260120/enwiki-20260120-pages-articles.xml.bz2",
    "expected_md5": "abc123...",
    "expected_sha1": "def456..."
  },
  "result": {
    "local_path": "/data/dumps/enwiki/enwiki-20260120-pages-articles.xml.bz2",
    "size_bytes": 2684354560,
    "download_duration_seconds": 120,
    "calculated_md5": "abc123...",
    "calculated_sha1": "def456...",
    "checksum_verified": true
  },
  "logs_path": "/data/logs/job_2.log",
  "parent_job": {
    "id": 1,
    "job_type": "discover_wikis",
    "status": "completed"
  },
  "child_jobs": [
    {
      "id": 50,
      "job_type": "upload_ia",
      "status": "in_progress"
    }
  ]
}
```

**Status Codes**:
- `200 OK`: Success
- `404 Not Found`: Job not found

---

### List Dumps

**GET** `/api/v1/dumps`

Get paginated list of dump files.

**Query Parameters**:
- `cycle_date` (string, optional): Filter by cycle (YYYY-MM-DD)
- `project` (string, optional): Filter by project (e.g., `wikipedia`)
- `language` (string, optional): Filter by language (e.g., `en`)
- `dump_type` (string, optional): Filter by dump type (e.g., `pages-articles`)
- `our_status` (string, optional): Filter by status
  - Values: `pending`, `downloading`, `downloaded`, `uploading`, `uploaded`, `included`, `failed`
- `cursor` (integer, optional): Dump ID to start from
- `limit` (integer, optional): Results per page (default: 100, max: 1000)

**Response**:
```json
{
  "dumps": [
    {
      "id": 123,
      "project": "wikipedia",
      "language": "en",
      "wiki_db_name": "enwiki",
      "cycle_date": "2026-01-20",
      "dump_type": "pages-articles",
      "filename": "enwiki-20260120-pages-articles.xml.bz2",
      "is_history": false,
      "size_bytes": 2684354560,
      "md5": "abc123...",
      "sha1": "def456...",
      "sha256": "789xyz...",
      "wikimedia_url": "https://dumps.wikimedia.org/enwiki/20260120/enwiki-20260120-pages-articles.xml.bz2",
      "ia_identifier": "wikiseed-enwiki-20260120",
      "ia_url": "https://archive.org/download/wikiseed-enwiki-20260120/enwiki-20260120-pages-articles.xml.bz2",
      "archive_today_url": "https://archive.today/2026.01.20-123456/https://dumps.wikimedia.org/enwiki/20260120/",
      "wikimedia_status": "done",
      "our_status": "uploaded",
      "discovered_at": "2026-01-20T00:02:00Z",
      "downloaded_at": "2026-01-20T00:07:30Z",
      "uploaded_at": "2026-01-20T00:12:45Z"
    }
  ],
  "pagination": {
    "cursor": 123,
    "limit": 100,
    "has_more": true,
    "next_cursor": 223
  }
}
```

**Status Codes**:
- `200 OK`: Success
- `400 Bad Request`: Invalid query parameters

---

### Get Dump Details

**GET** `/api/v1/dumps/{id}`

Get detailed information about a specific dump file.

**Path Parameters**:
- `id` (integer): Dump ID

**Response**:
```json
{
  "id": 123,
  "project": "wikipedia",
  "language": "en",
  "wiki_db_name": "enwiki",
  "cycle_date": "2026-01-20",
  "dump_type": "pages-articles",
  "filename": "enwiki-20260120-pages-articles.xml.bz2",
  "is_history": false,
  "size_bytes": 2684354560,
  "size_human": "2.5 GB",
  "md5": "abc123...",
  "sha1": "def456...",
  "sha256": "789xyz...",
  "wikimedia_url": "https://dumps.wikimedia.org/enwiki/20260120/enwiki-20260120-pages-articles.xml.bz2",
  "local_path": "/data/dumps/enwiki/enwiki-20260120-pages-articles.xml.bz2",
  "ia_identifier": "wikiseed-enwiki-20260120",
  "ia_url": "https://archive.org/download/wikiseed-enwiki-20260120/enwiki-20260120-pages-articles.xml.bz2",
  "archive_today_url": "https://archive.today/2026.01.20-123456/https://dumps.wikimedia.org/enwiki/20260120/",
  "wikimedia_status": "done",
  "our_status": "uploaded",
  "wikimedia_date": "2026-01-20T18:00:00Z",
  "discovered_at": "2026-01-20T00:02:00Z",
  "downloaded_at": "2026-01-20T00:07:30Z",
  "uploaded_at": "2026-01-20T00:12:45Z",
  "error_message": null,
  "related_jobs": [
    {
      "id": 2,
      "job_type": "download_dump",
      "status": "completed"
    },
    {
      "id": 50,
      "job_type": "upload_ia",
      "status": "completed"
    }
  ],
  "in_torrents": [
    {
      "id": 1,
      "name": "wikimedia-dumps-2026-01-20",
      "path_in_torrent": "compressed/en/wikipedia/enwiki-20260120-pages-articles.xml.bz2"
    }
  ]
}
```

**Status Codes**:
- `200 OK`: Success
- `404 Not Found`: Dump not found

---

### List Torrents

**GET** `/api/v1/torrents`

Get list of created torrents.

**Query Parameters**:
- `cycle_date` (string, optional): Filter by cycle (YYYY-MM-DD)
- `is_compressed` (boolean, optional): Filter by compression (true/false)
- `is_history` (boolean, optional): Filter history torrents (true/false)
- `published` (boolean, optional): Filter by publish status (true/false)

**Response**:
```json
{
  "torrents": [
    {
      "id": 1,
      "name": "wikimedia-dumps-2026-01-20",
      "filename": "wikimedia-dumps-2026-01-20.torrent",
      "cycle_date": "2026-01-20",
      "is_compressed": true,
      "is_history": false,
      "info_hash": "abc123def456...",
      "magnet_link": "magnet:?xt=urn:btih:abc123def456...&dn=wikimedia-dumps-2026-01-20&tr=...",
      "total_size_bytes": 912680550400,
      "total_size_human": "850 GB",
      "file_count": 450,
      "piece_count": 53100,
      "torrent_url": "https://r2.wikiseed.app/torrents/wikimedia-dumps-2026-01-20.torrent",
      "published": true,
      "published_at": "2026-01-20T18:00:00Z",
      "created_at": "2026-01-20T16:00:00Z",
      "latest_stats": {
        "seeders": 15,
        "leechers": 3,
        "completed": 127,
        "recorded_at": "2026-01-21T12:00:00Z"
      }
    }
  ]
}
```

**Status Codes**:
- `200 OK`: Success

---

### Get Torrent Details

**GET** `/api/v1/torrents/{id}`

Get detailed information about a specific torrent.

**Path Parameters**:
- `id` (integer): Torrent ID

**Response**:
```json
{
  "id": 1,
  "name": "wikimedia-dumps-2026-01-20",
  "filename": "wikimedia-dumps-2026-01-20.torrent",
  "cycle_date": "2026-01-20",
  "is_compressed": true,
  "is_history": false,
  "info_hash": "abc123def456...",
  "magnet_link": "magnet:?xt=urn:btih:abc123def456...&dn=wikimedia-dumps-2026-01-20&tr=udp://tracker.opentrackr.org:1337/announce&tr=...",
  "piece_size_bytes": 16777216,
  "piece_count": 53100,
  "total_size_bytes": 912680550400,
  "total_size_human": "850 GB",
  "file_count": 450,
  "torrent_file_path": "/data/torrents/wikimedia-dumps-2026-01-20.torrent",
  "torrent_url": "https://r2.wikiseed.app/torrents/wikimedia-dumps-2026-01-20.torrent",
  "trackers": [
    "udp://tracker.opentrackr.org:1337/announce",
    "udp://open.stealth.si:80/announce",
    "udp://tracker.torrent.eu.org:451/announce"
  ],
  "webseeds": [
    "https://archive.org/download/wikiseed-enwiki-20260120/",
    "https://dumps.wikimedia.org/"
  ],
  "published": true,
  "published_at": "2026-01-20T18:00:00Z",
  "created_at": "2026-01-20T16:00:00Z",
  "files": [
    {
      "dump_id": 123,
      "path_in_torrent": "compressed/en/wikipedia/enwiki-20260120-pages-articles.xml.bz2",
      "size_bytes": 2684354560,
      "project": "wikipedia",
      "language": "en",
      "dump_type": "pages-articles"
    }
  ],
  "stats_history": [
    {
      "seeders": 15,
      "leechers": 3,
      "completed": 127,
      "recorded_at": "2026-01-21T12:00:00Z"
    },
    {
      "seeders": 12,
      "leechers": 5,
      "completed": 115,
      "recorded_at": "2026-01-21T06:00:00Z"
    }
  ]
}
```

**Status Codes**:
- `200 OK`: Success
- `404 Not Found`: Torrent not found

---

### Get Seeding Statistics

**GET** `/api/v1/stats/seeding`

Get aggregate seeding statistics across all torrents.

**Query Parameters**:
- `since` (string, optional): Start date for stats (ISO 8601)

**Response**:
```json
{
  "total_torrents": 24,
  "total_seeders": 245,
  "total_leechers": 38,
  "total_completed": 1842,
  "average_seeders_per_torrent": 10.2,
  "torrents_with_zero_seeders": 0,
  "most_seeded": {
    "torrent_id": 15,
    "name": "wikimedia-dumps-2025-12-20",
    "seeders": 42,
    "leechers": 8
  },
  "least_seeded": {
    "torrent_id": 3,
    "name": "wikimedia-dumps-2025-01-20",
    "seeders": 3,
    "leechers": 0
  },
  "recorded_at": "2026-01-21T12:00:00Z"
}
```

**Status Codes**:
- `200 OK`: Success

---

## Data Models

### Job

```typescript
{
  id: integer,
  job_type: "discover_wikis" | "download_dump" | "upload_ia" | "create_torrent" | "publish_manifest",
  status: "pending" | "in_progress" | "completed" | "failed",
  cycle_date: string (YYYY-MM-DD),
  dump_id?: integer,
  parent_job_id?: integer,
  created_at: string (ISO 8601),
  started_at?: string (ISO 8601),
  completed_at?: string (ISO 8601),
  retry_count: integer,
  max_retries: integer,
  next_retry_at?: string (ISO 8601),
  last_error?: string,
  params: object,
  result?: object,
  logs_path?: string
}
```

### Dump

```typescript
{
  id: integer,
  project: string,
  language: string,
  wiki_db_name: string,
  cycle_date: string (YYYY-MM-DD),
  dump_type: string,
  filename: string,
  is_history: boolean,
  size_bytes: integer,
  size_human?: string,
  md5?: string,
  sha1?: string,
  sha256?: string,
  wikimedia_url: string,
  local_path?: string,
  ia_identifier?: string,
  ia_url?: string,
  archive_today_url?: string,
  wikimedia_status: "done" | "failed" | "in-progress" | null,
  our_status: "pending" | "downloading" | "downloaded" | "uploading" | "uploaded" | "included" | "failed",
  wikimedia_date?: string (ISO 8601),
  discovered_at: string (ISO 8601),
  downloaded_at?: string (ISO 8601),
  uploaded_at?: string (ISO 8601),
  error_message?: string
}
```

### Torrent

```typescript
{
  id: integer,
  name: string,
  filename: string,
  cycle_date: string (YYYY-MM-DD),
  is_compressed: boolean,
  is_history: boolean,
  info_hash: string,
  magnet_link: string,
  piece_size_bytes: integer,
  piece_count: integer,
  total_size_bytes: integer,
  total_size_human: string,
  file_count: integer,
  torrent_file_path: string,
  torrent_url?: string,
  trackers: string[],
  webseeds: string[],
  published: boolean,
  published_at?: string (ISO 8601),
  created_at: string (ISO 8601)
}
```

### TorrentStats

```typescript
{
  seeders: integer,
  leechers: integer,
  completed: integer,
  recorded_at: string (ISO 8601)
}
```

---

## Error Handling

### Error Response Format

All errors return a consistent JSON structure:

```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Job with ID 999 not found",
    "timestamp": "2026-01-21T12:00:00Z"
  }
}
```

### Error Codes

| HTTP Status | Code | Description |
|-------------|------|-------------|
| 400 | `BAD_REQUEST` | Invalid query parameters or request format |
| 404 | `NOT_FOUND` | Resource not found |
| 500 | `INTERNAL_ERROR` | Unexpected server error |
| 503 | `SERVICE_UNAVAILABLE` | Database connection failed |

### Common Errors

**Invalid Pagination**:
```json
{
  "error": {
    "code": "BAD_REQUEST",
    "message": "limit must be between 1 and 1000",
    "timestamp": "2026-01-21T12:00:00Z"
  }
}
```

**Resource Not Found**:
```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Torrent with ID 999 not found",
    "timestamp": "2026-01-21T12:00:00Z"
  }
}
```

---

## Interactive Documentation

### Swagger UI

Interactive API documentation is available at:

**URL**: `http://localhost:8000/api/docs`

**Features**:
- Try endpoints directly in browser
- View request/response schemas
- Copy curl commands
- Export OpenAPI spec

### OpenAPI Specification

Download the OpenAPI 3.0 spec:

**URL**: `http://localhost:8000/api/openapi.json`

Use with external tools like Postman, Insomnia, or code generators.

---

## Implementation Details

### Flask Application Structure

```python
# src/monitor/app.py

from flask import Flask, jsonify, render_template, request
from flasgger import Swagger

app = Flask(__name__)
swagger = Swagger(app)

# Web UI routes
@app.route('/')
def dashboard():
    """Render dashboard HTML"""
    return render_template('dashboard.html')

@app.route('/jobs')
def jobs_page():
    """Render jobs list HTML"""
    return render_template('jobs.html')

# API routes
@app.route('/api/v1/health')
def health():
    """
    Health Check
    ---
    responses:
      200:
        description: Service is healthy
        schema:
          type: object
          properties:
            status:
              type: string
              example: healthy
    """
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'version': '1.0.0'
    })

@app.route('/api/v1/jobs')
def list_jobs():
    """
    List Jobs
    ---
    parameters:
      - name: job_type
        in: query
        type: string
        required: false
      - name: status
        in: query
        type: string
        required: false
      - name: cursor
        in: query
        type: integer
        required: false
      - name: limit
        in: query
        type: integer
        required: false
        default: 100
    responses:
      200:
        description: List of jobs
    """
    # Query database with filters
    # Implement cursor-based pagination
    # Return JSON response
    pass
```

### Database Queries

**Cursor-based pagination**:

```python
def get_jobs(cursor=None, limit=100, filters=None):
    conn = sqlite3.connect('/data/db/jobs.db')
    conn.row_factory = sqlite3.Row

    query = "SELECT * FROM jobs WHERE 1=1"
    params = []

    # Apply filters
    if filters.get('job_type'):
        query += " AND job_type = ?"
        params.append(filters['job_type'])

    if filters.get('status'):
        query += " AND status = ?"
        params.append(filters['status'])

    # Cursor pagination
    if cursor:
        query += " AND id > ?"
        params.append(cursor)

    query += " ORDER BY id ASC LIMIT ?"
    params.append(limit + 1)  # Fetch one extra to check has_more

    cursor = conn.execute(query, params)
    rows = cursor.fetchall()

    has_more = len(rows) > limit
    if has_more:
        rows = rows[:limit]

    jobs = [dict(row) for row in rows]
    next_cursor = jobs[-1]['id'] if jobs and has_more else None

    return jobs, next_cursor, has_more
```

### Frontend Templates

**Simple HTML with vanilla JavaScript**:

```html
<!-- templates/dashboard.html -->
<!DOCTYPE html>
<html>
<head>
    <title>WikiSeed Monitor</title>
    <link rel="stylesheet" href="/static/style.css">
</head>
<body>
    <h1>WikiSeed Monitor</h1>
    <div id="status"></div>

    <script>
        async function loadStatus() {
            const response = await fetch('/api/v1/status');
            const data = await response.json();
            document.getElementById('status').innerHTML = `
                <p>Current Cycle: ${data.current_cycle_date}</p>
                <p>System Health: ${data.system_health}</p>
                <p>Jobs: ${data.job_summary.completed} completed,
                   ${data.job_summary.failed} failed</p>
            `;
        }

        loadStatus();
        setInterval(loadStatus, 10000);  // Refresh every 10s
    </script>
</body>
</html>
```

---

## Usage Examples

### cURL Examples

**Get system status**:
```bash
curl http://localhost:8000/api/v1/status
```

**List failed jobs**:
```bash
curl "http://localhost:8000/api/v1/jobs?status=failed&limit=10"
```

**Get specific dump details**:
```bash
curl http://localhost:8000/api/v1/dumps/123
```

**List torrents for a cycle**:
```bash
curl "http://localhost:8000/api/v1/torrents?cycle_date=2026-01-20"
```

### Python Examples

```python
import requests

# Get system status
response = requests.get('http://localhost:8000/api/v1/status')
status = response.json()
print(f"Current cycle: {status['current_cycle_date']}")

# Paginate through all jobs
cursor = None
all_jobs = []

while True:
    params = {'limit': 100}
    if cursor:
        params['cursor'] = cursor

    response = requests.get('http://localhost:8000/api/v1/jobs', params=params)
    data = response.json()

    all_jobs.extend(data['jobs'])

    if not data['pagination']['has_more']:
        break

    cursor = data['pagination']['next_cursor']

print(f"Total jobs: {len(all_jobs)}")
```

### JavaScript Examples

```javascript
// Fetch and display jobs
async function loadJobs() {
    const response = await fetch('/api/v1/jobs?status=in_progress');
    const data = await response.json();

    const jobsList = document.getElementById('jobs-list');
    jobsList.innerHTML = data.jobs.map(job => `
        <div class="job">
            <strong>${job.job_type}</strong> - ${job.status}
            <br>Created: ${job.created_at}
        </div>
    `).join('');
}

// Auto-refresh
setInterval(loadJobs, 5000);
```

---

## Related Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md): Container architecture and monitor service design
- [DATABASE.md](DATABASE.md): Database schema for jobs, dumps, torrents
- [DEPLOYMENT.md](DEPLOYMENT.md): Deploying the monitor service
- [DEVELOPMENT.md](DEVELOPMENT.md): Developing and testing the monitor
