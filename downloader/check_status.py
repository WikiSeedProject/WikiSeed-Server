#!/usr/bin/env python3
"""
Status checker for Wikimedia dumps downloader
Shows current download progress and statistics
"""

import sqlite3
import sys
from pathlib import Path
from datetime import datetime

# Import configuration
try:
    from config import DOWNLOAD_DIR
except ImportError:
    DOWNLOAD_DIR = Path.home() / "wikimedia_dumps"

DB_PATH = DOWNLOAD_DIR / "download_state.db"


def human_readable_size(size_bytes):
    """Convert bytes to human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


def get_stats():
    """Get comprehensive statistics"""
    if not DB_PATH.exists():
        print(f"Database not found at {DB_PATH}")
        print("Run the downloader script first!")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Overall stats
    cursor.execute('SELECT status, COUNT(*), SUM(size) FROM files GROUP BY status')
    status_stats = {}
    for row in cursor.fetchall():
        status_stats[row[0]] = {'count': row[1], 'size': row[2] or 0}
    
    cursor.execute('SELECT COUNT(*), SUM(size) FROM files')
    total_files, total_size = cursor.fetchone()
    total_size = total_size or 0
    
    # Recent activity
    cursor.execute('''
        SELECT COUNT(*) FROM files 
        WHERE completed_at IS NOT NULL 
        AND datetime(completed_at) > datetime('now', '-1 hour')
    ''')
    completed_last_hour = cursor.fetchone()[0]
    
    cursor.execute('''
        SELECT COUNT(*) FROM files 
        WHERE completed_at IS NOT NULL 
        AND datetime(completed_at) > datetime('now', '-24 hour')
    ''')
    completed_last_day = cursor.fetchone()[0]
    
    # Top wikis by file count
    cursor.execute('''
        SELECT 
            SUBSTR(url, LENGTH('https://dumps.wikimedia.org/other/mediawiki_content_history/') + 1,
                   INSTR(SUBSTR(url, LENGTH('https://dumps.wikimedia.org/other/mediawiki_content_history/') + 1), '/') - 1) as wiki,
            COUNT(*) as file_count,
            SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_count,
            SUM(size) as total_size
        FROM files
        GROUP BY wiki
        ORDER BY total_size DESC
        LIMIT 10
    ''')
    top_wikis = cursor.fetchall()
    
    # Failed files
    cursor.execute('''
        SELECT url, retry_count, last_attempt 
        FROM files 
        WHERE status = 'failed'
        LIMIT 20
    ''')
    failed_files = cursor.fetchall()
    
    conn.close()
    
    # Print statistics
    print("\n" + "="*80)
    print("WIKIMEDIA DUMPS DOWNLOAD STATUS")
    print("="*80)
    print(f"Database: {DB_PATH}")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    
    print("\n📊 OVERALL PROGRESS")
    print("-" * 80)
    print(f"Total files discovered:     {total_files:,}")
    print(f"Total size:                 {human_readable_size(total_size)}")
    
    completed = status_stats.get('completed', {}).get('count', 0)
    completed_size = status_stats.get('completed', {}).get('size', 0)
    
    if total_files > 0:
        pct_files = (completed / total_files) * 100
        pct_size = (completed_size / total_size) * 100 if total_size > 0 else 0
        
        print(f"\nCompleted:                  {completed:,} files ({pct_files:.1f}%)")
        print(f"                            {human_readable_size(completed_size)} ({pct_size:.1f}%)")
    
    pending = status_stats.get('pending', {}).get('count', 0)
    pending_size = status_stats.get('pending', {}).get('size', 0)
    print(f"\nPending:                    {pending:,} files")
    print(f"                            {human_readable_size(pending_size)}")
    
    downloading = status_stats.get('downloading', {}).get('count', 0)
    if downloading > 0:
        print(f"\nCurrently downloading:      {downloading:,} files")
    
    failed = status_stats.get('failed', {}).get('count', 0)
    if failed > 0:
        failed_size = status_stats.get('failed', {}).get('size', 0)
        print(f"\nFailed (max retries):       {failed:,} files")
        print(f"                            {human_readable_size(failed_size)}")
    
    print("\n⏱️  RECENT ACTIVITY")
    print("-" * 80)
    print(f"Completed in last hour:     {completed_last_hour:,} files")
    print(f"Completed in last 24h:      {completed_last_day:,} files")
    
    if completed_last_hour > 0 and pending > 0:
        hours_remaining = pending / completed_last_hour
        print(f"Estimated time remaining:   ~{hours_remaining:.1f} hours (based on last hour's rate)")
    
    print("\n📚 TOP 10 WIKIS BY SIZE")
    print("-" * 80)
    print(f"{'Wiki':<20} {'Total Files':>12} {'Completed':>12} {'Size':>15}")
    print("-" * 80)
    
    for wiki, file_count, completed_count, size in top_wikis:
        wiki_name = wiki if wiki else 'unknown'
        size_str = human_readable_size(size or 0)
        pct = (completed_count / file_count * 100) if file_count > 0 else 0
        print(f"{wiki_name:<20} {file_count:>12,} {completed_count:>12,} ({pct:>5.1f}%) {size_str:>15}")
    
    if failed_files:
        print("\n❌ FAILED FILES (showing first 20)")
        print("-" * 80)
        for url, retry_count, last_attempt in failed_files[:20]:
            filename = url.split('/')[-1]
            print(f"  • {filename}")
            print(f"    Retries: {retry_count}, Last attempt: {last_attempt}")
            print(f"    URL: {url}")
    
    print("\n" + "="*80)
    
    # Recommendations
    if failed > 0:
        print("\n💡 RECOMMENDATIONS:")
        print(f"  • {failed} files failed after max retries")
        print(f"  • Check download.log for detailed error messages")
        print(f"  • You can reset failed files to retry them:")
        print(f"    sqlite3 {DB_PATH} \"UPDATE files SET status='pending', retry_count=0 WHERE status='failed';\"")
    
    if pending > 0:
        print("\n💡 TO CONTINUE DOWNLOADING:")
        print(f"  • Run: python3 wikimedia_downloader.py")
        print(f"  • {pending:,} files remaining")
    
    if pending == 0 and failed == 0:
        print("\n🎉 ALL DOWNLOADS COMPLETE!")
        print(f"  • {completed:,} files successfully downloaded")
        print(f"  • Total size: {human_readable_size(completed_size)}")
    
    print("\n")


def main():
    """Main entry point"""
    if len(sys.argv) > 1:
        if sys.argv[1] == '--watch':
            # Watch mode - update every 10 seconds
            import time
            try:
                while True:
                    print("\033[2J\033[H")  # Clear screen
                    get_stats()
                    print("Refreshing in 10 seconds... (Ctrl+C to exit)")
                    time.sleep(10)
            except KeyboardInterrupt:
                print("\nExiting watch mode.")
                return
    
    get_stats()


if __name__ == "__main__":
    main()
