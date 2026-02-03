#!/bin/bash
# Wikimedia Dumps Downloader - Maintenance Utilities
# Common tasks for managing the downloader

# Activate virtual environment if it exists (for macOS)
if [ -d "$(dirname "$0")/venv" ]; then
    source "$(dirname "$0")/venv/bin/activate"
fi

DOWNLOAD_DIR="$HOME/wikimedia_dumps"  # Change this to match your DOWNLOAD_DIR
DB_PATH="$DOWNLOAD_DIR/download_state.db"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

show_help() {
    cat << EOF
Wikimedia Dumps Downloader - Maintenance Utilities

Usage: $0 [COMMAND]

Commands:
    status          Show download progress (same as check_status.py)
    watch           Monitor progress in real-time (updates every 10s)
    reset-failed    Reset all failed downloads to retry them
    check-space     Check available disk space
    clean-partial   Remove partial downloads (use with caution!)
    stats           Show detailed database statistics
    failed-list     List all failed files
    recent          Show recently completed downloads
    help            Show this help message

Examples:
    $0 status           # Quick status check
    $0 watch            # Real-time monitoring
    $0 reset-failed     # Retry all failed downloads
    $0 check-space      # Check if you have enough space

EOF
}

check_db() {
    if [ ! -f "$DB_PATH" ]; then
        echo -e "${RED}Error: Database not found at $DB_PATH${NC}"
        echo "Run the downloader script first!"
        exit 1
    fi
}

show_status() {
    python3 "$(dirname "$0")/check_status.py"
}

watch_status() {
    python3 "$(dirname "$0")/check_status.py" --watch
}

reset_failed() {
    check_db
    
    failed_count=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM files WHERE status='failed';")
    
    if [ "$failed_count" -eq 0 ]; then
        echo -e "${GREEN}No failed downloads to reset.${NC}"
        exit 0
    fi
    
    echo -e "${YELLOW}Found $failed_count failed downloads.${NC}"
    echo -e "This will reset them to retry. Continue? (y/N)"
    read -r response
    
    if [[ "$response" =~ ^[Yy]$ ]]; then
        sqlite3 "$DB_PATH" "UPDATE files SET status='pending', retry_count=0 WHERE status='failed';"
        echo -e "${GREEN}✓ Reset $failed_count files. Run the downloader to retry them.${NC}"
    else
        echo "Cancelled."
    fi
}

check_space() {
    echo -e "${BLUE}=== Disk Space Analysis ===${NC}\n"
    
    # Check where download dir is mounted
    mount_point=$(df "$DOWNLOAD_DIR" | tail -1 | awk '{print $6}')
    echo "Download directory: $DOWNLOAD_DIR"
    echo "Mounted at: $mount_point"
    echo
    
    # Show disk usage
    df -h "$DOWNLOAD_DIR" | tail -1 | awk '{
        printf "Total:      %s\n", $2
        printf "Used:       %s (%s)\n", $3, $5
        printf "Available:  %s\n", $4
    }'
    echo
    
    # Calculate download directory size
    if [ -d "$DOWNLOAD_DIR" ]; then
        echo "Calculating download directory size..."
        dir_size=$(du -sh "$DOWNLOAD_DIR" 2>/dev/null | cut -f1)
        echo "Current downloads: $dir_size"
        echo
    fi
    
    # Check database for total size needed
    if [ -f "$DB_PATH" ]; then
        check_db
        
        total_size=$(sqlite3 "$DB_PATH" "SELECT SUM(size) FROM files;")
        pending_size=$(sqlite3 "$DB_PATH" "SELECT SUM(size) FROM files WHERE status != 'completed';")
        
        if [ -n "$total_size" ] && [ "$total_size" != "0" ]; then
            total_gb=$(echo "scale=2; $total_size / 1024 / 1024 / 1024" | bc)
            echo "Total dump size: ${total_gb} GB"
            
            if [ -n "$pending_size" ] && [ "$pending_size" != "0" ]; then
                pending_gb=$(echo "scale=2; $pending_size / 1024 / 1024 / 1024" | bc)
                echo "Still to download: ${pending_gb} GB"
                
                # Check if we have enough space
                available_bytes=$(df "$DOWNLOAD_DIR" | tail -1 | awk '{print $4}')
                available_gb=$(echo "scale=2; $available_bytes / 1024 / 1024" | bc)
                
                if (( $(echo "$pending_size > $available_bytes * 1024" | bc -l) )); then
                    echo -e "\n${RED}⚠️  WARNING: Not enough space!${NC}"
                    echo "Need: ${pending_gb} GB"
                    echo "Have: ${available_gb} GB"
                else
                    echo -e "\n${GREEN}✓ Sufficient space available${NC}"
                fi
            fi
        fi
    fi
}

clean_partial() {
    check_db
    
    echo -e "${YELLOW}⚠️  WARNING: This will delete all partial downloads!${NC}"
    echo "Partial downloads are files that failed or are still downloading."
    echo "This cannot be undone. Continue? (y/N)"
    read -r response
    
    if [[ "$response" =~ ^[Yy]$ ]]; then
        # Get list of files that are not completed
        sqlite3 "$DB_PATH" "SELECT local_path FROM files WHERE status != 'completed';" | while read -r filepath; do
            if [ -f "$filepath" ]; then
                echo "Deleting: $filepath"
                rm -f "$filepath"
            fi
        done
        
        # Reset their status in database
        sqlite3 "$DB_PATH" "UPDATE files SET status='pending', retry_count=0 WHERE status IN ('downloading', 'failed');"
        
        echo -e "${GREEN}✓ Cleaned partial downloads${NC}"
    else
        echo "Cancelled."
    fi
}

show_stats() {
    check_db
    
    echo -e "${BLUE}=== Database Statistics ===${NC}\n"
    
    sqlite3 -column -header "$DB_PATH" << EOF
-- Status breakdown
SELECT 
    status,
    COUNT(*) as count,
    ROUND(SUM(size) / 1024.0 / 1024.0 / 1024.0, 2) as size_gb
FROM files
GROUP BY status;
EOF
    
    echo -e "\n--- Files by retry count ---"
    sqlite3 -column -header "$DB_PATH" << EOF
SELECT 
    retry_count,
    COUNT(*) as count
FROM files
GROUP BY retry_count
ORDER BY retry_count;
EOF
    
    echo -e "\n--- Top 20 wikis by file count ---"
    sqlite3 -column -header "$DB_PATH" << EOF
SELECT 
    SUBSTR(url, LENGTH('https://dumps.wikimedia.org/other/mediawiki_content_history/') + 1,
           INSTR(SUBSTR(url, LENGTH('https://dumps.wikimedia.org/other/mediawiki_content_history/') + 1), '/') - 1) as wiki,
    COUNT(*) as files,
    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
    ROUND(SUM(size) / 1024.0 / 1024.0 / 1024.0, 2) as size_gb
FROM files
GROUP BY wiki
ORDER BY files DESC
LIMIT 20;
EOF
}

list_failed() {
    check_db
    
    echo -e "${BLUE}=== Failed Downloads ===${NC}\n"
    
    sqlite3 -column -header "$DB_PATH" << EOF
SELECT 
    url,
    retry_count,
    last_attempt
FROM files
WHERE status = 'failed'
ORDER BY last_attempt DESC;
EOF
}

show_recent() {
    check_db
    
    echo -e "${BLUE}=== Recently Completed Downloads ===${NC}\n"
    
    sqlite3 -column -header "$DB_PATH" << EOF
SELECT 
    SUBSTR(url, -50) as filename,
    ROUND(size / 1024.0 / 1024.0, 2) as size_mb,
    completed_at
FROM files
WHERE status = 'completed'
    AND completed_at IS NOT NULL
ORDER BY completed_at DESC
LIMIT 50;
EOF
}

# Main script logic
case "${1:-help}" in
    status)
        show_status
        ;;
    watch)
        watch_status
        ;;
    reset-failed)
        reset_failed
        ;;
    check-space)
        check_space
        ;;
    clean-partial)
        clean_partial
        ;;
    stats)
        show_stats
        ;;
    failed-list)
        list_failed
        ;;
    recent)
        show_recent
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo -e "${RED}Unknown command: $1${NC}"
        echo "Run '$0 help' for usage information"
        exit 1
        ;;
esac