# GitHub Workflow Guide

## Initial Setup on GitHub

### 1. Create Repository on GitHub
```bash
# On GitHub.com, create a new repository named 'wikimedia-downloader'
# Don't initialize with README (you already have files)
```

### 2. Push Your Code (First Time)
```bash
# On your local machine where you have the files
cd ~/wikimedia-downloader  # or wherever your files are

# Initialize git if not already done
git init

# Add the .gitignore
cp .gitignore.example .gitignore  # Use the provided .gitignore

# Add all files except those in .gitignore
git add .

# Make initial commit
git commit -m "Initial commit: Wikimedia dumps downloader"

# Add your GitHub repo as remote
git remote add origin https://github.com/yourusername/wikimedia-downloader.git

# Push to GitHub
git push -u origin main  # or 'master' if that's your default branch
```

## On Your Ubuntu Server

### First Time Setup
```bash
# Clone the repository
cd ~
git clone https://github.com/yourusername/wikimedia-downloader.git
cd wikimedia-downloader

# Run setup (this creates your local config.py)
./setup.sh

# Your config.py is now local-only (not tracked by git)
# Start downloading
./wikimedia_downloader.py
```

### Getting Updates

**Simple method:**
```bash
cd ~/wikimedia-downloader
./update.sh  # Uses the smart update script
```

**Manual method:**
```bash
cd ~/wikimedia-downloader
git pull origin main
```

## Important: Keep config.py Local

Your `config.py` contains server-specific settings (like your 24TB drive path). **Don't commit it to GitHub!**

The `.gitignore` file prevents this:
```
config.py  # Never committed
```

Instead, commit a template:
```bash
# Create a template version (one time on your dev machine)
cp config.py config.py.example

# Edit config.py.example to have placeholder values
nano config.py.example
# Change: DOWNLOAD_DIR = Path("/mnt/bigdrive/wikimedia_dumps")
# To:     DOWNLOAD_DIR = Path.home() / "wikimedia_dumps"  # CHANGE THIS

# Commit the template
git add config.py.example
git commit -m "Add config template"
git push
```

Then on your server:
```bash
git pull
cp config.py.example config.py
nano config.py  # Set your actual paths
```

## Making Changes

### On Your Dev Machine
```bash
# Make changes to code
nano wikimedia_downloader.py

# Test locally
./wikimedia_downloader.py

# Commit and push
git add wikimedia_downloader.py
git commit -m "Add feature: XYZ"
git push origin main
```

### On Your Server
```bash
# Pull the changes
./update.sh
# or
git pull origin main

# Your config.py is preserved automatically
```

## Common Workflows

### Add a New Feature
```bash
# On dev machine
git checkout -b new-feature
# Make changes
git add .
git commit -m "Add new feature"
git push origin new-feature

# On GitHub: Create pull request, merge

# On server
git checkout main
git pull origin main
```

### Update Dependencies
```bash
# On dev machine
pip3 install some-new-package
pip3 freeze > requirements.txt
git add requirements.txt
git commit -m "Update dependencies"
git push

# On server
git pull
pip3 install -r requirements.txt
```

### Fix a Bug on Server
```bash
# On server, make quick fix
nano wikimedia_downloader.py

# Commit it
git add wikimedia_downloader.py
git commit -m "Fix: XYZ issue"
git push origin main

# On dev machine, pull the fix
git pull origin main
```

## File Tracking Strategy

**Always commit to GitHub:**
- `wikimedia_downloader.py`
- `check_status.py`
- `maintain.sh`
- `setup.sh`
- `update.sh`
- `requirements.txt`
- `README.md`
- `config.py.example` (template)
- `.gitignore`

**Never commit (in .gitignore):**
- `config.py` (server-specific)
- `download_state.db` (state file)
- `*.log` (logs)
- `wikimedia_dumps/` (the downloads)

## Best Practices

1. **Keep config.py local** - Each server has its own
2. **Use config.py.example** - Template for new deployments
3. **Test before pushing** - Don't break production
4. **Use branches** - For experimental features
5. **Update regularly** - `./update.sh` weekly

## Troubleshooting

### Merge Conflict in config.py
```bash
# This shouldn't happen if .gitignore is set up correctly
# But if it does:
git checkout --ours config.py  # Keep your version
git add config.py
git commit
```

### Lost Local Changes
```bash
# They're in the stash
git stash list
git stash apply stash@{0}
```

### Reset to GitHub Version
```bash
# Dangerous! Loses all local changes
git fetch origin
git reset --hard origin/main
# Then re-run ./setup.sh to create config.py
```

### Check What Will Update
```bash
git fetch origin
git log HEAD..origin/main --oneline
# Shows commits you don't have yet
```

## Multi-Server Deployment

If you have multiple servers downloading:

```bash
# Server 1: Content Current, English only
./setup.sh
# Choose: Content Current
# Edit config.py: WIKI_FILTER = ["enwiki"]

# Server 2: Content History, all wikis
./setup.sh
# Choose: Content History
# Leave filters empty

# Both stay in sync with code updates
# But have different configs
```

## Summary

```bash
# Development machine → GitHub
git add .
git commit -m "Update"
git push origin main

# GitHub → Ubuntu server
cd ~/wikimedia-downloader
./update.sh

# That's it! Your config.py is safe, code is updated.
```
