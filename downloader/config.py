"""
Configuration for Wikimedia Dumps Downloader
Edit this file to change what you're downloading
"""

from pathlib import Path

# ============================================================================
# DUMP SOURCE - Choose what to download
# ============================================================================

# Option 1: Content History (full edit history - HUGE)
# BASE_URL = "https://dumps.wikimedia.org/other/mediawiki_content_history/"

# Option 2: Content Current (current revisions only - much smaller)
BASE_URL = "https://dumps.wikimedia.org/other/mediawiki_content_current/"

# Option 3: Any other Wikimedia dump location
# BASE_URL = "https://dumps.wikimedia.org/backup-index.html"  # Won't work, just example
# BASE_URL = "https://dumps.wikimedia.org/enwiki/latest/"     # Single wiki dumps

# ============================================================================
# DOWNLOAD SETTINGS
# ============================================================================

# Where to save downloads (will be set by setup.sh)
DOWNLOAD_DIR = Path.home() / "wikimedia_dumps"

# Concurrent downloads (10-30 recommended for 1Gb connection)
MAX_CONCURRENT_DOWNLOADS = 15

# Download chunk size in bytes
CHUNK_SIZE = 1024 * 1024  # 1MB

# Retry settings
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds between retries

# ============================================================================
# FILTERING (optional)
# ============================================================================

# Only download specific wikis (empty list = download all)
# Examples:
#   WIKI_FILTER = ["enwiki"]  # Only English Wikipedia
#   WIKI_FILTER = ["enwiki", "dewiki", "frwiki"]  # English, German, French
#   WIKI_FILTER = []  # Download everything (default)
WIKI_FILTER = []

# Only download specific dates (empty list = download all)
# Examples:
#   DATE_FILTER = ["2026-01-01"]  # Only January 2026 dumps
#   DATE_FILTER = ["2026"]  # All dumps from 2026
#   DATE_FILTER = []  # Download all dates (default)
DATE_FILTER = []

# Skip certain file types (empty list = download everything)
# Examples:
#   SKIP_EXTENSIONS = [".xml.bz2"]  # Skip compressed XML files
#   SKIP_EXTENSIONS = [".json"]  # Skip JSON files
#   SKIP_EXTENSIONS = []  # Download everything (default)
SKIP_EXTENSIONS = []

# ============================================================================
# ADVANCED SETTINGS
# ============================================================================

# Enable debug logging
DEBUG = False

# User agent for requests
USER_AGENT = "WikimediaDownloader/1.0 (Educational/Archival Use)"

# Connection timeout (seconds)
TIMEOUT_TOTAL = 3600  # 1 hour
TIMEOUT_CONNECT = 60
TIMEOUT_READ = 300

# ============================================================================
# NOTES
# ============================================================================

# Content History vs Content Current:
#
# Content History (/mediawiki_content_history/):
#   - Contains FULL edit history of all revisions
#   - Much larger (10-20+ TB total)
#   - Complete historical record
#   - Multiple files per wiki per date
#
# Content Current (/mediawiki_content_current/):
#   - Contains ONLY current revisions (latest version of each page)
#   - Much smaller (typically 1-2 TB total)
#   - Single file per wiki per date
#   - Good for getting current state without history
#
# Choose based on your needs:
#   - Research/analysis of current state → use content_current
#   - Historical analysis/complete archive → use content_history
