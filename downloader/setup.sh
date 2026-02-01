#!/bin/bash
# Installation script for Wikimedia Dumps Downloader

set -e

echo "==========================================="
echo "Wikimedia Dumps Downloader - Setup"
echo "==========================================="
echo

# Check Python version
echo "Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed"
    echo "Install with: sudo apt install python3 python3-pip"
    exit 1
fi

python_version=$(python3 --version | cut -d' ' -f2)
echo "✓ Found Python $python_version"

# Check pip
if ! command -v pip3 &> /dev/null; then
    echo "Error: pip3 is not installed"
    echo "Install with: sudo apt install python3-pip"
    exit 1
fi
echo "✓ Found pip3"

# Install dependencies
echo
echo "Installing Python dependencies..."
pip3 install -r requirements.txt

echo
echo "✓ Dependencies installed"

# Ask about dump type
echo
echo "==========================================="
echo "Dump Type Selection"
echo "==========================================="
echo
echo "Which dumps do you want to download?"
echo
echo "1) Content Current (recommended - current revisions only, ~1-2 TB total)"
echo "   - Latest version of each Wikipedia page"
echo "   - Much smaller and faster"
echo "   - Good for most research/analysis needs"
echo
echo "2) Content History (full edit history, ~10-20+ TB total)"
echo "   - Complete edit history of all revisions"
echo "   - Massive download, takes weeks"
echo "   - Only needed for historical analysis"
echo
read -p "Choose (1 or 2) [1]: " dump_choice
dump_choice=${dump_choice:-1}

if [ "$dump_choice" = "1" ]; then
    base_url="https://dumps.wikimedia.org/other/mediawiki_content_current/"
    echo "✓ Selected: Content Current (smaller, current revisions only)"
elif [ "$dump_choice" = "2" ]; then
    base_url="https://dumps.wikimedia.org/other/mediawiki_content_history/"
    echo "✓ Selected: Content History (larger, full edit history)"
    echo "⚠️  Warning: This is a MASSIVE download (10-20+ TB)"
else
    echo "Invalid choice, defaulting to Content Current"
    base_url="https://dumps.wikimedia.org/other/mediawiki_content_current/"
fi

# Ask for download directory
echo
echo "==========================================="
echo "Configuration"
echo "==========================================="
echo
echo "Where should the dumps be downloaded?"
echo "Enter the full path to your 24TB drive mount point"
echo "(Example: /mnt/bigdrive or /media/yourusername/WD24TB)"
read -p "Download path: " download_path

# Validate path
if [ ! -d "$download_path" ]; then
    echo "Warning: Directory $download_path does not exist"
    read -p "Create it? (y/N) " create_dir
    if [[ "$create_dir" =~ ^[Yy]$ ]]; then
        mkdir -p "$download_path/wikimedia_dumps"
        echo "✓ Created directory"
    else
        echo "Please create the directory first and re-run setup"
        exit 1
    fi
else
    download_path="$download_path/wikimedia_dumps"
    mkdir -p "$download_path"
fi

# Check disk space
echo
echo "Checking available disk space..."
available_space=$(df -BG "$download_path" | tail -1 | awk '{print $4}' | sed 's/G//')
echo "Available space: ${available_space} GB"

if [ "$available_space" -lt 5000 ]; then
    echo "⚠️  Warning: You have less than 5TB available"
    echo "The full dump set may require 10-20+ TB"
    read -p "Continue anyway? (y/N) " continue_anyway
    if [[ ! "$continue_anyway" =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Update configuration
echo
echo "Updating configuration files..."

# Update config.py
sed -i "s|^BASE_URL = .*|BASE_URL = \"$base_url\"|" config.py
sed -i "s|^DOWNLOAD_DIR = .*|DOWNLOAD_DIR = Path(\"$download_path\")|" config.py

# Update maintenance script
sed -i "s|DOWNLOAD_DIR=\"\$HOME/wikimedia_dumps\"|DOWNLOAD_DIR=\"$download_path\"|" maintain.sh

echo "✓ Configuration updated"

# Ask about concurrent downloads
echo
read -p "How many concurrent downloads? (default: 15, recommended: 10-20): " concurrent
concurrent=${concurrent:-15}

if [ "$concurrent" -gt 0 ] && [ "$concurrent" -le 50 ]; then
    sed -i "s|^MAX_CONCURRENT_DOWNLOADS = .*|MAX_CONCURRENT_DOWNLOADS = $concurrent|" config.py
    echo "✓ Set to $concurrent concurrent downloads"
else
    echo "Using default: 15 concurrent downloads"
fi

# Create download directory
mkdir -p "$download_path"

# Summary
echo
echo "==========================================="
echo "Setup Complete!"
echo "==========================================="
echo
echo "Configuration:"
echo "  Dump type: $([ "$dump_choice" = "1" ] && echo "Content Current (smaller)" || echo "Content History (larger)")"
echo "  Source URL: $base_url"
echo "  Download directory: $download_path"
echo "  Concurrent downloads: ${concurrent:-15}"
echo "  Database: $download_path/download_state.db"
echo "  Log file: $download_path/download.log"
echo
echo "Next steps:"
echo "  1. Start downloading:"
echo "     ./wikimedia_downloader.py"
echo
echo "  2. Check status:"
echo "     ./check_status.py"
echo "     or"
echo "     ./maintain.sh status"
echo
echo "  3. Monitor in real-time:"
echo "     ./maintain.sh watch"
echo
echo "Useful commands:"
echo "  ./maintain.sh help          - Show all maintenance commands"
echo "  ./maintain.sh check-space   - Check disk space"
echo "  ./maintain.sh reset-failed  - Retry failed downloads"
echo
echo "Advanced:"
echo "  Edit config.py to:"
echo "    - Switch between dump types (content_current vs content_history)"
echo "    - Filter specific wikis or dates"
echo "    - Adjust download settings"
echo "  See SWITCHING_DUMPS.md for details"
echo
echo "⚠️  Important notes:"
if [ "$dump_choice" = "1" ]; then
    echo "  - Content Current: ~1-2 TB for all wikis"
    echo "  - Should take 2-4 days with your connection"
else
    echo "  - Content History: ~10-20+ TB for all wikis"
    echo "  - May take several days to weeks"
fi
echo "  - You can stop and resume anytime (Ctrl+C)"
echo "  - Run the downloader again to get new dumps"
echo "  - Edit config.py to switch dump types or filter wikis"
echo
echo "Ready to start!"
echo
