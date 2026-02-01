# Switching Between Dump Types

The downloader works with **any** Wikimedia dumps directory. Here are the most common ones:

## Available Dump Types

### 1. Content Current (Recommended to start)
**URL**: `https://dumps.wikimedia.org/other/mediawiki_content_current/`

- ✅ Contains ONLY the current/latest revision of each page
- ✅ Much smaller: ~1-2 TB total for all wikis
- ✅ Single file per wiki per date
- ✅ Good for getting current state of Wikipedia
- ✅ Faster to download

**Use case**: Research, analysis, or just want the current state of all wikis

### 2. Content History (Complete Archive)
**URL**: `https://dumps.wikimedia.org/other/mediawiki_content_history/`

- ⚠️ Contains FULL edit history of ALL revisions
- ⚠️ Massive: 10-20+ TB for all wikis
- ⚠️ Multiple files per wiki per date
- ⚠️ Takes days/weeks to download
- ✅ Complete historical record

**Use case**: Historical analysis, research requiring full edit history, complete archival

### 3. Regular Dumps (Per-wiki current dumps)
**URL**: `https://dumps.wikimedia.org/backup-index.html`

- Individual wiki dumps
- Contains current + some recent history
- More flexible date options
- Can pick specific wikis easily

## How to Switch

### Option 1: Edit config.py (Recommended)

Edit `config.py` and change the `BASE_URL`:

```python
# For current revisions only (smaller, faster):
BASE_URL = "https://dumps.wikimedia.org/other/mediawiki_content_current/"

# For full edit history (huge):
# BASE_URL = "https://dumps.wikimedia.org/other/mediawiki_content_history/"
```

Then just run the downloader:
```bash
./wikimedia_downloader.py
```

### Option 2: Use Filters

You can also filter what gets downloaded in `config.py`:

```python
# Only download English Wikipedia
WIKI_FILTER = ["enwiki"]

# Only download latest dumps
DATE_FILTER = ["2026-01-01"]

# Skip certain file types
SKIP_EXTENSIONS = [".json"]
```

## Size Comparison

Here's roughly what you'd download for ALL wikis:

| Dump Type | Approximate Size | Time (1Gb fiber) |
|-----------|-----------------|------------------|
| Content Current | 1-2 TB | 2-4 days |
| Content History | 10-20+ TB | 2-4 weeks |

## Recommendations

### For Most Users:
**Start with Content Current** - it's much more manageable and contains everything you need for most use cases.

```python
BASE_URL = "https://dumps.wikimedia.org/other/mediawiki_content_current/"
WIKI_FILTER = []  # Get all wikis
DATE_FILTER = ["2026-01"]  # Get latest month only
```

### For Complete Archival:
**Content History** - but be prepared for a massive download.

```python
BASE_URL = "https://dumps.wikimedia.org/other/mediawiki_content_history/"
WIKI_FILTER = []  # Get all wikis
DATE_FILTER = []  # Get all dates
```

### For Specific Research:
**Filter to what you need**

```python
BASE_URL = "https://dumps.wikimedia.org/other/mediawiki_content_current/"
WIKI_FILTER = ["enwiki", "dewiki", "frwiki"]  # Just these 3 wikis
DATE_FILTER = ["2026-01-01"]  # Just this date
```

## Incremental Updates

The beauty of this system is you can:

1. **Start small**: Download content_current for just a few wikis
2. **Add more**: Change filters and run again - it only downloads new files
3. **Switch types**: Change BASE_URL and run - separate directory structure
4. **Monthly updates**: Run monthly to get new dumps - incremental only

## Example Workflow

### Day 1: Start with something manageable
```python
# config.py
BASE_URL = "https://dumps.wikimedia.org/other/mediawiki_content_current/"
WIKI_FILTER = ["enwiki"]  # Just English Wikipedia
DATE_FILTER = ["2026-01"]
```
Downloads: ~50-100 GB in a few hours

### Week 1: Add more wikis
```python
# config.py
WIKI_FILTER = ["enwiki", "dewiki", "frwiki", "jawiki"]
```
Run again - downloads only the new wikis

### Month 1: Get all current wikis
```python
# config.py
WIKI_FILTER = []  # Remove filter
```
Run again - downloads all remaining wikis

### Month 2: Get latest dumps
Run again - automatically gets new January dumps, doesn't re-download existing

### Later: Switch to history if needed
```python
# config.py
BASE_URL = "https://dumps.wikimedia.org/other/mediawiki_content_history/"
```
Run - downloads to different directory structure (separate from current)

## Quick Commands

```bash
# See what you'd download without actually downloading
# (Comment out download_all() in main() first)

# Start with just one wiki to test
python3 -c "
from config import *
WIKI_FILTER = ['enwiki']
DATE_FILTER = ['2026-01-01']
" && ./wikimedia_downloader.py

# Check size before committing
./maintain.sh check-space
```

## The Files You'll Get

### Content Current Structure:
```
enwiki/
  2026-01-01/
    xml/
      bzip2/
        enwiki-2026-01-01-pages-articles.xml.bz2  (~20 GB)
        SHA256SUMS
```

### Content History Structure:
```
enwiki/
  2026-01-01/
    xml/
      bzip2/
        enwiki-2026-01-01-p1p100.xml.bz2          (~500 MB)
        enwiki-2026-01-01-p101p200.xml.bz2        (~500 MB)
        ... (hundreds of files totaling ~2-3 TB)
        SHA256SUMS
```

---

**Bottom line**: Start with `content_current`, it's much more reasonable in size and contains what most people need!
