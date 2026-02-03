#!/bin/bash
# Wrapper script to run wikimedia_downloader.py
# Automatically activates virtual environment on macOS

# Detect if venv exists (macOS setup)
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run the downloader
python3 wikimedia_downloader.py "$@"