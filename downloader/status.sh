#!/bin/bash
# Wrapper script to run check_status.py
# Automatically activates virtual environment on macOS

# Detect if venv exists (macOS setup)
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run the status checker
python3 check_status.py "$@"