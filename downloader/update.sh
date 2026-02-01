#!/bin/bash
# Update script - pulls latest from GitHub while preserving local config

set -e

echo "==========================================="
echo "Updating Wikimedia Downloader from GitHub"
echo "==========================================="
echo

# Check if we're in a git repository
if [ ! -d .git ]; then
    echo "Error: Not in a git repository"
    echo "Run this from your cloned directory"
    exit 1
fi

# Backup current config if it exists
if [ -f config.py ]; then
    echo "Backing up current config.py..."
    cp config.py config.py.backup
    echo "✓ Saved to config.py.backup"
fi

# Check for uncommitted changes
if ! git diff-index --quiet HEAD --; then
    echo
    echo "You have uncommitted local changes:"
    git status --short
    echo
    read -p "Stash these changes and continue? (y/N) " stash_changes
    
    if [[ "$stash_changes" =~ ^[Yy]$ ]]; then
        git stash
        echo "✓ Changes stashed"
        STASHED=true
    else
        echo "Update cancelled. Commit or stash your changes first."
        exit 1
    fi
fi

# Pull latest changes
echo
echo "Pulling latest changes from GitHub..."
if git pull origin main 2>/dev/null || git pull origin master 2>/dev/null; then
    echo "✓ Updated successfully"
else
    echo "✗ Pull failed"
    exit 1
fi

# Restore stashed changes if any
if [ "$STASHED" = true ]; then
    echo
    echo "Restoring your stashed changes..."
    if git stash pop; then
        echo "✓ Changes restored"
    else
        echo "⚠️  Conflicts detected. Resolve manually with:"
        echo "   git status"
        echo "   git stash list"
    fi
fi

# If config was backed up and new config exists, ask what to do
if [ -f config.py.backup ] && [ -f config.py ]; then
    echo
    echo "Config file handling:"
    echo "  - config.py.backup = Your previous settings"
    echo "  - config.py = New version from GitHub"
    echo
    echo "What do you want to do?"
    echo "1) Keep your old config (restore from backup)"
    echo "2) Use new config (you'll need to reconfigure)"
    echo "3) Keep both (manual merge needed)"
    read -p "Choice (1/2/3) [1]: " config_choice
    config_choice=${config_choice:-1}
    
    case $config_choice in
        1)
            mv config.py config.py.new
            mv config.py.backup config.py
            echo "✓ Restored your previous config"
            echo "  New template saved as config.py.new"
            ;;
        2)
            echo "✓ Using new config from GitHub"
            echo "  Old config saved as config.py.backup"
            echo "⚠️  You'll need to run ./setup.sh or edit config.py"
            ;;
        3)
            echo "✓ Both configs preserved"
            echo "  - config.py = new from GitHub"
            echo "  - config.py.backup = your old settings"
            echo "  Compare them with: diff config.py config.py.backup"
            ;;
    esac
fi

# Check if requirements changed
if git diff HEAD@{1} HEAD --name-only | grep -q requirements.txt; then
    echo
    echo "⚠️  requirements.txt changed"
    read -p "Update Python dependencies? (y/N) " update_deps
    if [[ "$update_deps" =~ ^[Yy]$ ]]; then
        pip3 install -r requirements.txt
        echo "✓ Dependencies updated"
    fi
fi

echo
echo "==========================================="
echo "Update Complete!"
echo "==========================================="
echo
echo "Next steps:"
echo "  - Review config.py to ensure your settings are correct"
echo "  - Check for any breaking changes in the commit history"
echo "  - Run ./wikimedia_downloader.py when ready"
echo
