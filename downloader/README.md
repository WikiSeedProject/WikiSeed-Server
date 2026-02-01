# Wikimedia Content History Dumps Downloader

## Overview
This script downloads all Wikimedia content history dumps from https://dumps.wikimedia.org/other/mediawiki_content_history/ with full resume support, checksum verification, and incremental update capabilities.

## Features
- ✅ Async/parallel downloads (15 concurrent by default)
- ✅ Resume interrupted downloads automatically
- ✅ SHA256 checksum verification
- ✅ Incremental updates (only download new dumps)
- ✅ SQLite database tracks all download state
- ✅ Automatic retry with exponential backoff (3 attempts)
- ✅ Progress logging to file and terminal
- ✅ Handles 400+ wikis and multiple date dumps

## Installationq

### 1. Install Python dependencies
```bash
pip3 install -r requirements.txt
```

### 2. Configure download location
Edit `wikimedia_downloader.py` and change this line:
```python
DOWNLOAD_DIR = Path.home() / "wikimedia_dumps"  # Change to your 24TB mount point
```

For example, if your 24TB drive is mounted at `/mnt/bigdrive`:
```python
DOWNLOAD_DIR = Path("/mnt/bigdrive/wikimedia_dumps")
```

## Usage

### First Run (Full Download)
```bash
python3 wikimedia_downloader.py
```

This will:
1. Discover all files across all wikis and dates
2. Create a SQLite database to track progress
3. Begin downloading with 15 parallel downloads
4. Verify checksums as files complete
5. Automatically resume if interrupted

### Subsequent Runs (Incremental Updates)
Simply run the script again:
```bash
python3 wikimedia_downloader.py
```

The script will:
- Discover any new dumps (new dates, new wikis)
- Only download files not already completed
- Resume any interrupted downloads
- Retry any previously failed downloads (up to 3 attempts total)

### Monitoring Progress

The script logs to both:
- **Terminal**: Real-time progress
- **Log file**: `download.log` in the download directory

### Stopping and Resuming

Press `Ctrl+C` to stop. The script will:
- Save all progress to the database
- Allow clean resume on next run
- Preserve partial downloads (they'll resume from where they stopped)

## Configuration Options

Edit these constants in `wikimedia_downloader.py`:

```python
MAX_CONCURRENT_DOWNLOADS = 15  # Parallel downloads
CHUNK_SIZE = 1024 * 1024      # Download chunk size (1MB)
MAX_RETRIES = 3                # Retry attempts per file
RETRY_DELAY = 5                # Initial delay between retries (seconds)
```

## Database Structure

The SQLite database (`download_state.db`) tracks:
- **files table**: Every file with URL, path, size, checksum, status, retry count
- **checksums table**: SHA256SUMS file contents for verification

## Expected Download Size

⚠️ **Warning**: This is a MASSIVE download (likely 10-20+ TB)

Major wikis by size (approximate):
- English Wikipedia (enwiki): ~2-3 TB per dump
- German Wikipedia (dewiki): ~500+ GB per dump
- French Wikipedia (frwiki): ~400+ GB per dump
- Japanese Wikipedia (jawiki): ~300+ GB per dump
- Plus 400+ other wikis

## Directory Structure

Downloads preserve the original structure:
```
wikimedia_dumps/
├── abwiki/
│   ├── 2025-11-01/
│   │   └── xml/
│   │       └── bzip2/
│   │           ├── SHA256SUMS
│   │           └── abwiki-2025-11-01-p1p49770.xml.bz2
│   ├── 2025-12-01/
│   └── 2026-01-01/
├── enwiki/
│   └── ...
└── download_state.db
```

## Troubleshooting

### Check download stats
```bash
sqlite3 wikimedia_dumps/download_state.db "SELECT status, COUNT(*) FROM files GROUP BY status;"
```

### Find failed downloads
```bash
sqlite3 wikimedia_dumps/download_state.db "SELECT url FROM files WHERE status='failed';"
```

### Reset a specific file to retry
```bash
sqlite3 wikimedia_dumps/download_state.db "UPDATE files SET status='pending', retry_count=0 WHERE url='<URL>';"
```

### Check disk space
```bash
df -h /mnt/your-24tb-drive
```

### View recent activity
```bash
tail -f wikimedia_dumps/download.log
```

## Performance Tips

1. **Faster downloads**: Increase `MAX_CONCURRENT_DOWNLOADS` to 20-30 if your connection can handle it
2. **Lower server load**: Decrease to 5-10 if you want to be more conservative
3. **Disk I/O**: Make sure your 24TB drive is fast enough for concurrent writes
4. **Network**: Monitor with `iftop` or `nethogs` to see bandwidth usage

## Safety Features

- **Exponential backoff**: Failed downloads wait progressively longer before retry
- **Checksum verification**: Every file is verified against SHA256SUMS
- **Resume support**: Partial downloads continue from last byte
- **State persistence**: All progress saved to database
- **Error isolation**: One failed file doesn't stop others

## Estimated Runtime

With 1Gb fiber and 15 concurrent downloads:
- Initial discovery: 30-60 minutes
- Full download: Several days to weeks (depending on total size)
- Incremental updates: Minutes to hours (only new dumps)

## Notes

- The script is respectful to Wikimedia servers (15 concurrent is reasonable)
- Downloads are resumable - you can stop/start anytime
- Checksums ensure data integrity
- Failed downloads are automatically retried
- The database allows you to track exactly what you have

## Advanced Usage

### Download only specific wikis

Modify the `discover_all_files()` method to filter:
```python
# Only download English Wikipedia
if 'enwiki' not in url:
    return
```

### Download only latest dumps

Filter by date in `_discover_recursive()`:
```python
# Only download 2026-01-01 or later
if '2025' in item_rel_path:
    return  # Skip older dumps
```

### Check for new dumps without downloading

Comment out the download call in `main()`:
```python
# await downloader.download_all()  # Comment this out
```

Run to update the database with new files, then review before downloading.
