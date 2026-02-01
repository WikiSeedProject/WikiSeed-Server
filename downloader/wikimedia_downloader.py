#!/usr/bin/env python3
"""
WikiSeed Downloader
Downloads dumps from Wikimedia with resume support, checksum verification, and incremental updates.
"""

import asyncio
import aiohttp
import aiofiles
import hashlib
import sqlite3
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Set, Optional, Tuple
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import re
import time

# Import configuration
try:
    from config import (
        BASE_URL, DOWNLOAD_DIR, MAX_CONCURRENT_DOWNLOADS, CHUNK_SIZE,
        MAX_RETRIES, RETRY_DELAY, WIKI_FILTER, DATE_FILTER, SKIP_EXTENSIONS,
        DEBUG, USER_AGENT, TIMEOUT_TOTAL, TIMEOUT_CONNECT, TIMEOUT_READ
    )
except ImportError:
    # Fallback to defaults if config.py not found
    BASE_URL = "https://dumps.wikimedia.org/other/mediawiki_content_history/"
    DOWNLOAD_DIR = Path.home() / "wikimedia_dumps"
    MAX_CONCURRENT_DOWNLOADS = 15
    CHUNK_SIZE = 1024 * 1024
    MAX_RETRIES = 3
    RETRY_DELAY = 5
    WIKI_FILTER = []
    DATE_FILTER = []
    SKIP_EXTENSIONS = []
    DEBUG = False
    USER_AGENT = "WikiSeed.app/0.1"
    TIMEOUT_TOTAL = 3600
    TIMEOUT_CONNECT = 60
    TIMEOUT_READ = 300

DB_PATH = DOWNLOAD_DIR / "download_state.db"
LOG_FILE = DOWNLOAD_DIR / "download.log"

# Setup logging
logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages SQLite database for tracking download state"""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        """Initialize database schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS files (
                url TEXT PRIMARY KEY,
                local_path TEXT NOT NULL,
                size INTEGER,
                checksum TEXT,
                status TEXT DEFAULT 'pending',
                last_modified TEXT,
                retry_count INTEGER DEFAULT 0,
                last_attempt TEXT,
                completed_at TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS checksums (
                directory TEXT PRIMARY KEY,
                content TEXT,
                fetched_at TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_status ON files(status)
        ''')
        
        conn.commit()
        conn.close()
    
    def add_file(self, url: str, local_path: str, size: Optional[int] = None, 
                 last_modified: Optional[str] = None):
        """Add or update file record"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR IGNORE INTO files (url, local_path, size, last_modified)
            VALUES (?, ?, ?, ?)
        ''', (url, local_path, size, last_modified))
        
        conn.commit()
        conn.close()
    
    def update_file_status(self, url: str, status: str, checksum: Optional[str] = None):
        """Update file download status"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        now = datetime.utcnow().isoformat()
        
        if status == 'completed':
            cursor.execute('''
                UPDATE files 
                SET status = ?, checksum = ?, completed_at = ?
                WHERE url = ?
            ''', (status, checksum, now, url))
        else:
            cursor.execute('''
                UPDATE files 
                SET status = ?, last_attempt = ?
                WHERE url = ?
            ''', (status, now, url))
        
        conn.commit()
        conn.close()
    
    def increment_retry(self, url: str) -> int:
        """Increment retry count and return new count"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE files 
            SET retry_count = retry_count + 1,
                last_attempt = ?
            WHERE url = ?
        ''', (datetime.utcnow().isoformat(), url))
        
        cursor.execute('SELECT retry_count FROM files WHERE url = ?', (url,))
        result = cursor.fetchone()
        
        conn.commit()
        conn.close()
        
        return result[0] if result else 0
    
    def get_pending_files(self) -> List[Dict]:
        """Get all files that need downloading"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT url, local_path, size, retry_count
            FROM files
            WHERE status IN ('pending', 'failed', 'downloading')
            AND retry_count < ?
            ORDER BY retry_count ASC, size ASC
        ''', (MAX_RETRIES,))
        
        files = []
        for row in cursor.fetchall():
            files.append({
                'url': row[0],
                'local_path': row[1],
                'size': row[2],
                'retry_count': row[3]
            })
        
        conn.close()
        return files
    
    def get_stats(self) -> Dict:
        """Get download statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT status, COUNT(*) FROM files GROUP BY status')
        stats = dict(cursor.fetchall())
        
        cursor.execute('SELECT COUNT(*) FROM files')
        total = cursor.fetchone()[0]
        
        cursor.execute('SELECT SUM(size) FROM files WHERE status = "completed"')
        downloaded_bytes = cursor.fetchone()[0] or 0
        
        cursor.execute('SELECT SUM(size) FROM files')
        total_bytes = cursor.fetchone()[0] or 0
        
        conn.close()
        
        return {
            'total': total,
            'completed': stats.get('completed', 0),
            'pending': stats.get('pending', 0),
            'failed': stats.get('failed', 0),
            'downloading': stats.get('downloading', 0),
            'downloaded_bytes': downloaded_bytes,
            'total_bytes': total_bytes
        }
    
    def store_checksum_file(self, directory: str, content: str):
        """Store SHA256SUMS file content"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO checksums (directory, content, fetched_at)
            VALUES (?, ?, ?)
        ''', (directory, content, datetime.utcnow().isoformat()))
        
        conn.commit()
        conn.close()
    
    def get_checksum_for_file(self, directory: str, filename: str) -> Optional[str]:
        """Get expected checksum for a file"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT content FROM checksums WHERE directory = ?', (directory,))
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            return None
        
        # Parse SHA256SUMS format: "checksum  filename"
        for line in result[0].split('\n'):
            if filename in line:
                parts = line.split()
                if len(parts) >= 2:
                    return parts[0]
        
        return None


class WikimediaDownloader:
    """Main downloader class"""
    
    def __init__(self):
        self.db = DatabaseManager(DB_PATH)
        self.session: Optional[aiohttp.ClientSession] = None
        self.semaphore = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)
        self.download_dir = DOWNLOAD_DIR
        self.download_dir.mkdir(parents=True, exist_ok=True)
    
    async def __aenter__(self):
        timeout = aiohttp.ClientTimeout(
            total=TIMEOUT_TOTAL,
            connect=TIMEOUT_CONNECT,
            sock_read=TIMEOUT_READ
        )
        headers = {'User-Agent': USER_AGENT}
        self.session = aiohttp.ClientSession(timeout=timeout, headers=headers)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def fetch_directory_listing(self, url: str) -> List[Dict]:
        """Fetch and parse directory listing"""
        try:
            async with self.session.get(url) as response:
                if response.status != 200:
                    logger.error(f"Failed to fetch {url}: {response.status}")
                    return []
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                items = []
                for link in soup.find_all('a'):
                    href = link.get('href')
                    if not href or href == '../':
                        continue
                    
                    # Get size and date from the listing
                    parent = link.parent
                    text = parent.get_text()
                    
                    # Try to extract size (last column before the link)
                    size_match = re.search(r'(\d+)\s*$', text.split(href)[0])
                    size = int(size_match.group(1)) if size_match else None
                    
                    # Try to extract date
                    date_match = re.search(r'(\d{2}-\w{3}-\d{4}\s+\d{2}:\d{2})', text)
                    last_modified = date_match.group(1) if date_match else None
                    
                    items.append({
                        'name': href,
                        'url': urljoin(url, href),
                        'is_directory': href.endswith('/'),
                        'size': size,
                        'last_modified': last_modified
                    })
                
                return items
        
        except Exception as e:
            logger.error(f"Error fetching directory {url}: {e}")
            return []
    
    async def discover_all_files(self):
        """Recursively discover all files to download"""
        logger.info("Starting file discovery...")
        
        await self._discover_recursive(BASE_URL, "")
        
        stats = self.db.get_stats()
        logger.info(f"Discovery complete. Found {stats['total']} files "
                   f"({stats['total_bytes'] / 1024**3:.2f} GB)")
    
    async def _discover_recursive(self, url: str, rel_path: str):
        """Recursively discover files in directory tree"""
        items = await self.fetch_directory_listing(url)
        
        for item in items:
            item_rel_path = rel_path + item['name']
            
            if item['is_directory']:
                # Apply wiki filter (check first directory level)
                if WIKI_FILTER and '/' not in rel_path:
                    wiki_name = item['name'].rstrip('/')
                    if wiki_name not in WIKI_FILTER:
                        logger.debug(f"Skipping wiki (not in filter): {wiki_name}")
                        continue
                
                # Apply date filter (check if path contains date)
                if DATE_FILTER:
                    skip_date = True
                    for date_pattern in DATE_FILTER:
                        if date_pattern in item_rel_path:
                            skip_date = False
                            break
                    if skip_date:
                        logger.debug(f"Skipping date (not in filter): {item_rel_path}")
                        continue
                
                # Recursively explore subdirectory
                logger.info(f"Exploring: {item_rel_path}")
                await self._discover_recursive(item['url'], item_rel_path)
            else:
                # Apply extension filter
                if SKIP_EXTENSIONS:
                    skip_file = False
                    for ext in SKIP_EXTENSIONS:
                        if item['name'].endswith(ext):
                            logger.debug(f"Skipping file (extension filter): {item['name']}")
                            skip_file = True
                            break
                    if skip_file:
                        continue
                
                # Add file to database
                local_path = self.download_dir / item_rel_path
                self.db.add_file(
                    url=item['url'],
                    local_path=str(local_path),
                    size=item['size'],
                    last_modified=item['last_modified']
                )
                
                # If this is a SHA256SUMS file, fetch and store it
                if item['name'] == 'SHA256SUMS':
                    await self._fetch_checksum_file(item['url'], rel_path)
    
    async def _fetch_checksum_file(self, url: str, directory: str):
        """Fetch and store SHA256SUMS file"""
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    content = await response.text()
                    self.db.store_checksum_file(directory, content)
                    logger.debug(f"Stored checksums for {directory}")
        except Exception as e:
            logger.error(f"Error fetching checksum file {url}: {e}")
    
    async def download_file(self, url: str, local_path: str, expected_size: Optional[int] = None):
        """Download a single file with resume support"""
        local_path = Path(local_path)
        local_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Check if file exists and get current size
        resume_pos = 0
        if local_path.exists():
            resume_pos = local_path.stat().st_size
            
            # If file is complete (matches expected size), verify checksum
            if expected_size and resume_pos == expected_size:
                logger.debug(f"File exists with correct size: {local_path.name}")
                return True
        
        headers = {}
        mode = 'wb'
        
        if resume_pos > 0:
            headers['Range'] = f'bytes={resume_pos}-'
            mode = 'ab'
            logger.info(f"Resuming {local_path.name} from {resume_pos / 1024**2:.2f} MB")
        
        try:
            async with self.session.get(url, headers=headers) as response:
                if response.status not in [200, 206]:
                    logger.error(f"Failed to download {url}: {response.status}")
                    return False
                
                # Get total size
                content_length = response.headers.get('Content-Length')
                total_size = int(content_length) if content_length else None
                
                if total_size:
                    total_size += resume_pos
                
                async with aiofiles.open(local_path, mode) as f:
                    downloaded = resume_pos
                    last_log = time.time()
                    
                    async for chunk in response.content.iter_chunked(CHUNK_SIZE):
                        await f.write(chunk)
                        downloaded += len(chunk)
                        
                        # Log progress every 5 seconds
                        if time.time() - last_log > 5:
                            if total_size:
                                pct = (downloaded / total_size) * 100
                                logger.info(f"Downloading {local_path.name}: "
                                          f"{downloaded / 1024**2:.2f} MB / "
                                          f"{total_size / 1024**2:.2f} MB ({pct:.1f}%)")
                            else:
                                logger.info(f"Downloading {local_path.name}: "
                                          f"{downloaded / 1024**2:.2f} MB")
                            last_log = time.time()
                
                logger.info(f"✓ Downloaded: {local_path.name}")
                return True
        
        except Exception as e:
            logger.error(f"Error downloading {url}: {e}")
            return False
    
    async def verify_checksum(self, file_path: Path, directory: str) -> bool:
        """Verify file checksum against SHA256SUMS"""
        expected_checksum = self.db.get_checksum_for_file(directory, file_path.name)
        
        if not expected_checksum:
            logger.warning(f"No checksum available for {file_path.name}")
            return True  # Assume OK if no checksum available
        
        # Calculate actual checksum
        sha256_hash = hashlib.sha256()
        
        try:
            async with aiofiles.open(file_path, 'rb') as f:
                while True:
                    chunk = await f.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    sha256_hash.update(chunk)
            
            actual_checksum = sha256_hash.hexdigest()
            
            if actual_checksum == expected_checksum:
                logger.debug(f"✓ Checksum verified: {file_path.name}")
                return True
            else:
                logger.error(f"✗ Checksum mismatch for {file_path.name}")
                logger.error(f"  Expected: {expected_checksum}")
                logger.error(f"  Got:      {actual_checksum}")
                return False
        
        except Exception as e:
            logger.error(f"Error verifying checksum for {file_path.name}: {e}")
            return False
    
    async def download_with_retry(self, file_info: Dict):
        """Download a file with retry logic"""
        async with self.semaphore:
            url = file_info['url']
            local_path = file_info['local_path']
            expected_size = file_info['size']
            
            for attempt in range(MAX_RETRIES):
                try:
                    # Update status
                    self.db.update_file_status(url, 'downloading')
                    
                    # Download
                    success = await self.download_file(url, local_path, expected_size)
                    
                    if not success:
                        raise Exception("Download failed")
                    
                    # Verify checksum (skip for SHA256SUMS files)
                    local_path_obj = Path(local_path)
                    if local_path_obj.name != 'SHA256SUMS':
                        # Get directory for checksum lookup
                        rel_path = str(local_path_obj.relative_to(self.download_dir).parent) + '/'
                        
                        if not await self.verify_checksum(local_path_obj, rel_path):
                            raise Exception("Checksum verification failed")
                    
                    # Success!
                    checksum = None
                    if local_path_obj.name != 'SHA256SUMS':
                        sha256_hash = hashlib.sha256()
                        async with aiofiles.open(local_path, 'rb') as f:
                            while True:
                                chunk = await f.read(CHUNK_SIZE)
                                if not chunk:
                                    break
                                sha256_hash.update(chunk)
                        checksum = sha256_hash.hexdigest()
                    
                    self.db.update_file_status(url, 'completed', checksum)
                    return True
                
                except Exception as e:
                    retry_count = self.db.increment_retry(url)
                    
                    if retry_count >= MAX_RETRIES:
                        logger.error(f"Failed after {MAX_RETRIES} attempts: {url}")
                        self.db.update_file_status(url, 'failed')
                        
                        # Delete partial file
                        if Path(local_path).exists():
                            Path(local_path).unlink()
                        
                        return False
                    else:
                        logger.warning(f"Retry {retry_count}/{MAX_RETRIES} for {url}: {e}")
                        await asyncio.sleep(RETRY_DELAY * (2 ** retry_count))  # Exponential backoff
    
    async def download_all(self):
        """Download all pending files"""
        pending_files = self.db.get_pending_files()
        
        if not pending_files:
            logger.info("No files to download!")
            return
        
        logger.info(f"Starting download of {len(pending_files)} files...")
        
        # Create download tasks
        tasks = [self.download_with_retry(file_info) for file_info in pending_files]
        
        # Process downloads
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Log results
        successful = sum(1 for r in results if r is True)
        failed = len(results) - successful
        
        logger.info(f"Download complete: {successful} successful, {failed} failed")
    
    def print_stats(self):
        """Print download statistics"""
        stats = self.db.get_stats()
        
        print("\n" + "="*60)
        print("DOWNLOAD STATISTICS")
        print("="*60)
        print(f"Total files:      {stats['total']:,}")
        print(f"Completed:        {stats['completed']:,}")
        print(f"Pending:          {stats['pending']:,}")
        print(f"Failed:           {stats['failed']:,}")
        print(f"Downloaded:       {stats['downloaded_bytes'] / 1024**3:.2f} GB")
        print(f"Total size:       {stats['total_bytes'] / 1024**3:.2f} GB")
        
        if stats['total'] > 0:
            pct = (stats['completed'] / stats['total']) * 100
            print(f"Progress:         {pct:.1f}%")
        
        print("="*60 + "\n")


async def main():
    """Main entry point"""
    logger.info("="*60)
    logger.info("Wikimedia Dumps Downloader")
    logger.info("="*60)
    logger.info(f"Source URL: {BASE_URL}")
    logger.info(f"Download directory: {DOWNLOAD_DIR}")
    logger.info(f"Database: {DB_PATH}")
    logger.info(f"Log file: {LOG_FILE}")
    logger.info(f"Max concurrent downloads: {MAX_CONCURRENT_DOWNLOADS}")
    
    if WIKI_FILTER:
        logger.info(f"Wiki filter: {', '.join(WIKI_FILTER)}")
    else:
        logger.info("Wiki filter: None (downloading all wikis)")
    
    if DATE_FILTER:
        logger.info(f"Date filter: {', '.join(DATE_FILTER)}")
    else:
        logger.info("Date filter: None (downloading all dates)")
    
    if SKIP_EXTENSIONS:
        logger.info(f"Skipping extensions: {', '.join(SKIP_EXTENSIONS)}")
    
    logger.info("="*60 + "\n")
    
    async with WikimediaDownloader() as downloader:
        # Discover files (only adds new ones to database)
        await downloader.discover_all_files()
        
        # Print initial stats
        downloader.print_stats()
        
        # Download all pending files
        await downloader.download_all()
        
        # Print final stats
        downloader.print_stats()
    
    logger.info("All done!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\nDownload interrupted by user. Progress has been saved.")
        logger.info("Run the script again to resume.")
        sys.exit(0)
