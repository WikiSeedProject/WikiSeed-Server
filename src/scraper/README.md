# Scraper Module

The Scraper discovers available Wikimedia dumps and creates download jobs.

## Overview

The scraper is the first component in the WikiSeed pipeline. It:

1. Polls the database for `discover_wikis` jobs
2. Queries Wikimedia's dump API for available dumps
3. Archives dump index pages to archive.today
4. Stores dump metadata in the database
5. Creates `download_dump` jobs for each discovered file

## Architecture

- **`__main__.py`** - Entry point that starts the worker
- **`worker.py`** - Main worker loop and job processing logic
- **`wikimedia.py`** - Wikimedia dump API client
- **`archiver.py`** - archive.today integration for preserving dump pages

## Usage

### Running Standalone

```bash
python -m src.scraper
```

### Running in Docker

```bash
docker compose up scraper
```

## How It Works

### 1. Job Polling

The worker polls the database every 30 seconds for pending `discover_wikis` jobs:

```python
SELECT id, cycle_date, params
FROM jobs
WHERE job_type = 'discover_wikis'
  AND status = 'pending'
ORDER BY created_at ASC
LIMIT 1
```

### 2. Dump Discovery

For each wiki, the scraper:

1. Fetches `https://dumps.wikimedia.org/{wiki}/{YYYYMMDD}/dumpstatus.json`
2. Parses the JSON to find completed dump jobs
3. Extracts file metadata (name, size, checksums, URLs)

Example dumpstatus.json structure:
```json
{
  "jobs": {
    "articlesdump": {
      "status": "done",
      "files": {
        "enwiki-20260120-pages-articles.xml.bz2": {
          "size": 19234567890,
          "url": "https://dumps.wikimedia.org/enwiki/20260120/...",
          "md5": "abc123...",
          "sha1": "def456..."
        }
      }
    }
  }
}
```

### 3. Archive Preservation

For each wiki, the scraper submits the dump index page to archive.today:

- URL: `https://dumps.wikimedia.org/{wiki}/`
- Stores archive URL in `dumps.archive_today_url`
- Retries with exponential backoff on rate limits

### 4. Database Storage

Each discovered dump file is stored in the `dumps` table:

```sql
INSERT INTO dumps (
    project, language, wiki_db_name, cycle_date, dump_type, filename,
    is_history, size_bytes, md5, sha1, wikimedia_url, archive_today_url,
    wikimedia_status, our_status
) VALUES (...)
```

### 5. Download Job Creation

For each dump file, create a `download_dump` job:

```sql
INSERT INTO jobs (job_type, status, parent_job_id, dump_id, cycle_date)
VALUES ('download_dump', 'pending', ?, ?, ?)
```

## Configuration

The scraper respects these settings from `config.yaml`:

```yaml
wikiseed:
  scraper:
    poll_interval: 30           # Seconds between job polls
    rate_limit_rpm: 100         # Requests per minute to Wikimedia
    archive_enabled: true       # Enable archive.today archiving
```

## Job Parameters

The `discover_wikis` job accepts these parameters:

```json
{
  "wikis": ["enwiki", "frwiki"],  // Optional: specific wikis to process
  "test_mode": true                // Optional: process only 5 wikis for testing
}
```

## Error Handling

### Retry Logic

Failed jobs are retried with exponential backoff:

- Attempt 1: Immediate
- Attempt 2: +5 minutes
- Attempt 3: +15 minutes
- Attempt 4: +1 hour
- Attempt 5: +4 hours
- After 5 failures: Mark as `failed`

### Rate Limiting

- **Wikimedia API**: Max 100 requests/minute (0.6s delay between requests)
- **archive.today**: Automatic retry with 60s, 120s, 180s delays on 429 errors

## Metrics and Logging

The scraper logs:

- Number of wikis processed
- Number of dumps discovered
- Number of download jobs created
- API errors and retry attempts
- Rate limit hits

Example output:
```
2026-01-19 19:00:00 [INFO] scraper.worker: Processing discover_wikis job 123 for cycle 2026-01-20
2026-01-19 19:00:05 [INFO] scraper.worker: Discovering dumps for 10 wikis on cycle 2026-01-20
2026-01-19 19:00:15 [INFO] scraper.worker: Processed enwiki: 127 dumps discovered
2026-01-19 19:01:30 [INFO] scraper.worker: Discovery complete: 1247 dumps discovered, 1247 download jobs created
2026-01-19 19:01:30 [INFO] scraper.worker: Job 123 completed successfully
```

## Database Schema

### dumps Table (What Scraper Creates)

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| project | TEXT | Project type (wiki, wiktionary, etc.) |
| language | TEXT | Language code (en, fr, de, etc.) |
| wiki_db_name | TEXT | Wiki database name (enwiki, frwiki) |
| cycle_date | DATE | Dump cycle date (YYYY-MM-DD) |
| dump_type | TEXT | Dump job name (articlesdump, etc.) |
| filename | TEXT | Dump filename |
| is_history | BOOLEAN | Whether this is a full history dump |
| size_bytes | INTEGER | File size in bytes |
| md5 | TEXT | MD5 checksum |
| sha1 | TEXT | SHA1 checksum |
| wikimedia_url | TEXT | Wikimedia download URL |
| archive_today_url | TEXT | archive.today archive URL |
| wikimedia_status | TEXT | Status from Wikimedia (done) |
| our_status | TEXT | Our processing status (pending) |
| discovered_at | TIMESTAMP | When discovered |

### jobs Table (What Scraper Consumes and Creates)

The scraper:
- **Consumes**: `discover_wikis` jobs (status='pending')
- **Creates**: `download_dump` jobs (one per dump file)

## Testing

### Unit Tests

```bash
pytest tests/scraper/
```

### Integration Tests

```bash
# Test with a single small wiki
pytest tests/scraper/test_integration.py -k test_discover_single_wiki
```

### Manual Testing

Create a test job manually:

```sql
INSERT INTO jobs (job_type, cycle_date, params)
VALUES (
  'discover_wikis',
  '2026-01-20',
  '{"wikis": ["simplewiki"], "test_mode": true}'
);
```

Then run the scraper and check results:

```bash
docker compose logs -f scraper
```

## Next Steps

After the scraper completes:

1. **Downloader** picks up `download_dump` jobs and fetches files
2. **Uploader** uploads downloaded files to Internet Archive
3. **Creator** bundles files into torrents
4. **Publisher** publishes torrents to R2/Gist/etc.

## Troubleshooting

### No Dumps Found

- Check if the cycle date has dumps available on dumps.wikimedia.org
- Wikimedia typically creates dumps on the 1st and 20th of each month
- Not all wikis have dumps for every cycle

### Rate Limited by Wikimedia

- The scraper respects a 0.6s delay between requests (100 req/min)
- If rate limited, check logs for errors and adjust poll interval

### Archive.today Failures

- archive.today can be unreliable or rate-limited
- The scraper will retry but may fail after 3 attempts
- This is not critical - the dump can still be downloaded

### Database Lock Errors

- Ensure only one scraper container is running
- Check for long-running transactions in other components
- SQLite WAL mode should prevent most locks
