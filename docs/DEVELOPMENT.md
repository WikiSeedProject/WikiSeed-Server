# WikiSeed: Development Guide

## Overview

This guide covers local development setup, testing strategies, code quality standards, and contribution guidelines for WikiSeed.

## Table of Contents

- [Getting Started](#getting-started)
- [Project Structure](#project-structure)
- [Development Environment](#development-environment)
- [Testing](#testing)
- [Code Quality](#code-quality)
- [Debugging](#debugging)
- [Contributing](#contributing)

---

## Getting Started

### Prerequisites

- **Git**: For version control
- **Python**: 3.12 or higher
- **Docker**: Docker Engine 24.0+ and Docker Compose v2
- **Text Editor/IDE**: VS Code, PyCharm, or your preference

### Quick Start

```bash
# Clone repository
git clone https://github.com/yourusername/wikiseed-server.git
cd wikiseed-server

# Create Python virtual environment
python3.12 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install

# Copy example configuration
cp config.example.yaml config.yaml
cp .env.example .env
# Edit .env with test credentials (can use dummy values for local dev)

# Create data directories
mkdir -p data/{db,dumps,torrents,seeder/{config,watch}}

# Initialize database
python scripts/init_db.py

# Start development environment
docker compose -f docker-compose.dev.yml up -d

# Run tests
pytest

# Check code quality
make lint
```

---

## Project Structure

```
wikiseed-server/
├── .github/
│   └── workflows/
│       ├── ci.yml                  # CI/CD pipeline
│       └── release.yml             # Release automation
├── config/
│   ├── config.example.yaml         # Example configuration
│   └── small-wiki-mode.yaml        # Config for testing
├── data/                           # Created at runtime (gitignored)
│   ├── db/
│   │   └── jobs.db                 # SQLite database
│   ├── dumps/                      # Downloaded dump files
│   ├── torrents/                   # Created torrents
│   └── seeder/
│       ├── config/                 # qBittorrent config
│       └── watch/                  # Watch directory for .torrent files
├── migrations/
│   ├── 001_initial.sql             # Initial schema
│   └── 002_*.sql                   # Future migrations
├── scripts/
│   ├── init_db.py                  # Database initialization
│   ├── test_alert.py               # Test email alerts
│   └── backup_db.sh                # Backup script
├── src/
│   ├── common/                     # Shared utilities
│   │   ├── __init__.py
│   │   ├── config.py               # Config loading
│   │   ├── database.py             # Database connection/helpers
│   │   ├── logging.py              # Logging setup
│   │   └── retry.py                # Retry logic helpers
│   ├── controller/
│   │   ├── __init__.py
│   │   ├── controller.py           # Main controller loop
│   │   ├── scheduler.py            # Job scheduling logic
│   │   └── Dockerfile
│   ├── scraper/
│   │   ├── __init__.py
│   │   ├── scraper.py              # Main scraper loop
│   │   ├── wikimedia_api.py        # Wikimedia API client
│   │   ├── archive_today.py        # archive.today integration
│   │   └── Dockerfile
│   ├── downloader/
│   │   ├── __init__.py
│   │   ├── downloader.py           # Main downloader loop
│   │   ├── download_manager.py     # Download with resume/retry
│   │   ├── checksum.py             # Checksum verification
│   │   └── Dockerfile
│   ├── uploader/
│   │   ├── __init__.py
│   │   ├── uploader.py             # Main uploader loop
│   │   ├── ia_client.py            # Internet Archive API
│   │   └── Dockerfile
│   ├── creator/
│   │   ├── __init__.py
│   │   ├── creator.py              # Main creator loop
│   │   ├── torrent_builder.py      # Torrent creation logic
│   │   ├── metadata_generator.py   # Generate HASH.json, STATUS.json, etc.
│   │   └── Dockerfile
│   ├── publisher/
│   │   ├── __init__.py
│   │   ├── publisher.py            # Main publisher loop
│   │   ├── manifest_generator.py   # Create manifest.json
│   │   ├── r2_client.py            # Cloudflare R2 upload
│   │   ├── gist_client.py          # GitHub Gist upload
│   │   └── Dockerfile
│   └── monitor/
│       ├── __init__.py
│       ├── app.py                  # Flask/FastAPI web app
│       ├── templates/              # HTML templates
│       ├── static/                 # CSS/JS
│       └── Dockerfile
├── tests/
│   ├── __init__.py
│   ├── conftest.py                 # Pytest fixtures
│   ├── test_common/
│   │   ├── test_config.py
│   │   ├── test_database.py
│   │   └── test_retry.py
│   ├── test_scraper/
│   │   ├── test_scraper.py
│   │   └── test_wikimedia_api.py
│   ├── test_downloader/
│   │   ├── test_downloader.py
│   │   └── test_checksum.py
│   ├── test_creator/
│   │   ├── test_torrent_builder.py
│   │   └── test_metadata_generator.py
│   ├── test_integration/
│   │   ├── test_job_flow.py        # Integration tests
│   │   └── test_database_locking.py
│   └── small_wiki_mode/
│       ├── test_end_to_end.py      # Full pipeline test
│       └── tiny_wikis.txt          # List of tiny test wikis
├── docs/
│   ├── bigpicture.md               # Strategic overview
│   ├── ARCHITECTURE.md             # Technical architecture
│   ├── DATABASE.md                 # Database schema
│   ├── DEPLOYMENT.md               # Production deployment
│   ├── DEVELOPMENT.md              # This file
│   └── API.md                      # Monitor API reference (future)
├── .env.example                    # Example environment variables
├── .gitignore
├── .pre-commit-config.yaml         # Pre-commit hooks config
├── docker-compose.yml              # Production compose file
├── docker-compose.dev.yml          # Development compose file
├── Makefile                        # Common development tasks
├── pyproject.toml                  # Project metadata (minimal)
├── requirements.txt                # Production dependencies
├── requirements-dev.txt            # Development dependencies
├── LICENSE                         # AGPL-3.0
└── README.md                       # Project overview
```

### Directory Explanations

- **`src/`**: All Python source code, organized by container
- **`tests/`**: All test code, mirrors `src/` structure
- **`migrations/`**: Database schema migrations (numbered SQL files)
- **`scripts/`**: Utility scripts for operations
- **`config/`**: Configuration file templates
- **`docs/`**: All documentation (you are here!)

---

## Development Environment

### Docker Compose for Development

Development uses a separate `docker-compose.dev.yml` with these differences:

- **Volume mounts for live code reload**: Source code mounted into containers
- **Debug ports exposed**: For remote debugging
- **Faster iteration**: No need to rebuild containers for code changes
- **Test credentials**: Can use dummy API keys

**docker-compose.dev.yml** (simplified example):

```yaml
version: '3.8'

services:
  controller:
    build:
      context: .
      dockerfile: src/controller/Dockerfile
    volumes:
      - ./src:/app/src:ro          # Mount source code
      - ./config:/config:ro
      - ./data/db:/data/db
    env_file:
      - .env
    environment:
      - PYTHONUNBUFFERED=1
      - LOG_LEVEL=DEBUG            # Verbose logging
    command: python -u /app/src/controller/controller.py

  scraper:
    build:
      context: .
      dockerfile: src/scraper/Dockerfile
    volumes:
      - ./src:/app/src:ro
      - ./config:/config:ro
      - ./data/db:/data/db
    env_file:
      - .env
    environment:
      - PYTHONUNBUFFERED=1
      - LOG_LEVEL=DEBUG

  # ... similar for other containers

  # Development database browser
  db-browser:
    image: coleifer/sqlite-web
    ports:
      - "8001:8080"
    volumes:
      - ./data/db:/data:ro
    command: ["-H", "0.0.0.0", "/data/jobs.db"]
```

### Starting Development Environment

```bash
# Start all containers with logs
docker compose -f docker-compose.dev.yml up

# Start in background
docker compose -f docker-compose.dev.yml up -d

# Stop all containers
docker compose -f docker-compose.dev.yml down

# Rebuild after dependency changes
docker compose -f docker-compose.dev.yml build

# Restart specific container
docker compose -f docker-compose.dev.yml restart scraper
```

### Local Development Without Docker

For faster iteration on individual components:

```bash
# Activate virtual environment
source venv/bin/activate

# Set environment variables
export CONFIG_PATH=./config/config.yaml
export DATABASE_PATH=./data/db/jobs.db
export LOG_LEVEL=DEBUG

# Run specific worker
python src/scraper/scraper.py

# Or with auto-reload (for development)
watchmedo auto-restart -d src/scraper -p "*.py" -- python src/scraper/scraper.py
```

### Database Browser

Access SQLite database through web UI during development:

```bash
# Start sqlite-web
docker compose -f docker-compose.dev.yml up db-browser

# Open browser
open http://localhost:8001
```

### Makefile Commands

Common development tasks:

```makefile
# Makefile

.PHONY: help install test lint format clean

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install dependencies
	pip install --upgrade pip
	pip install -r requirements.txt
	pip install -r requirements-dev.txt
	pre-commit install

test:  ## Run tests
	pytest -v --cov=src --cov-report=html --cov-report=term

test-fast:  ## Run tests without coverage
	pytest -v -x

test-small-wiki:  ## Run small wiki mode end-to-end test
	pytest tests/small_wiki_mode/ -v -s

lint:  ## Run linters
	ruff check src/ tests/
	mypy src/

format:  ## Format code
	black src/ tests/
	ruff check --fix src/ tests/

clean:  ## Clean up generated files
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage

dev-up:  ## Start development environment
	docker compose -f docker-compose.dev.yml up -d

dev-down:  ## Stop development environment
	docker compose -f docker-compose.dev.yml down

dev-logs:  ## Tail development logs
	docker compose -f docker-compose.dev.yml logs -f

db-init:  ## Initialize database
	python scripts/init_db.py

db-shell:  ## Open database shell
	sqlite3 data/db/jobs.db

db-reset:  ## Reset database (WARNING: deletes all data!)
	rm -f data/db/jobs.db
	python scripts/init_db.py
```

**Usage**:
```bash
make help          # Show all commands
make install       # Set up environment
make test          # Run tests with coverage
make lint          # Check code quality
make format        # Format code
make dev-up        # Start development
```

---

## Testing

### Testing Philosophy

WikiSeed uses **small wiki mode** for end-to-end testing: running the full pipeline on tiny wikis (a few kilobytes) to validate the entire system in minutes.

**Testing Pyramid**:
1. **Unit tests** (fast, many): Test individual functions
2. **Integration tests** (medium, some): Test container interactions
3. **Small wiki mode** (slow, few): Full end-to-end validation

### Test Dependencies

```txt
# requirements-dev.txt

# Testing
pytest>=7.4.0
pytest-cov>=4.1.0
pytest-asyncio>=0.21.0
pytest-timeout>=2.1.0

# Code quality
black>=24.1.0
ruff>=0.1.11
mypy>=1.8.0
pre-commit>=3.6.0

# Development tools
ipython>=8.20.0
watchdog>=3.0.0  # For auto-reload
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html --cov-report=term

# Run specific test file
pytest tests/test_scraper/test_wikimedia_api.py

# Run specific test
pytest tests/test_scraper/test_wikimedia_api.py::test_fetch_dump_status

# Run tests matching pattern
pytest -k "downloader"

# Stop on first failure
pytest -x

# Verbose output
pytest -v

# Show print statements
pytest -s
```

### Small Wiki Mode Testing

**Purpose**: Validate entire pipeline with real Wikimedia APIs using tiny wikis.

**How it works**:
1. Select ~5 tiny wikis (e.g., `aawiki`, `abwiki` - a few MB each)
2. Run full pipeline: discover → download → upload → create torrent → publish
3. Verify all steps complete successfully
4. Clean up test data

**Configuration** (`config/small-wiki-mode.yaml`):

```yaml
wikiseed:
  testing:
    small_wiki_mode: true
    test_wikis:
      - aawiki      # Afar Wikipedia (~2 MB)
      - abwiki      # Abkhazian Wikipedia (~5 MB)
      - acewiki     # Acehnese Wikipedia (~8 MB)
    skip_upload_ia: false        # Set true to skip IA uploads
    skip_publish: false          # Set true to skip publishing
    cleanup_after: true          # Delete test data after run

  storage:
    dumps_path: /tmp/wikiseed-test/dumps
    torrents_path: /tmp/wikiseed-test/torrents
```

**Run small wiki mode**:

```bash
# Run small wiki mode test
pytest tests/small_wiki_mode/test_end_to_end.py -v -s

# Or via make
make test-small-wiki
```

**Expected output**:
```
tests/small_wiki_mode/test_end_to_end.py::test_full_pipeline
  ✓ Controller creates discover_wikis job
  ✓ Scraper discovers 3 wikis (aawiki, abwiki, acewiki)
  ✓ Scraper creates 15 download jobs
  ✓ Downloader fetches all 15 dumps
  ✓ Uploader uploads to Internet Archive
  ✓ Creator builds torrent
  ✓ Publisher generates manifest
  ✓ Cleanup successful
PASSED [100%]
```

**Small wiki mode test** (`tests/small_wiki_mode/test_end_to_end.py`):

```python
import pytest
import time
from pathlib import Path

def test_full_pipeline(dev_database, dev_config):
    """Run full pipeline on tiny wikis."""

    # 1. Controller creates discover job
    create_discover_job(cycle_date="2026-01-20")

    # 2. Wait for discovery to complete
    wait_for_job_completion(job_type="discover_wikis", timeout=60)

    # 3. Verify dumps were discovered
    dumps = get_dumps(cycle_date="2026-01-20")
    assert len(dumps) > 0, "No dumps discovered"

    # 4. Wait for all downloads to complete
    wait_for_all_downloads(timeout=300)  # 5 minutes

    # 5. Verify all downloads succeeded
    failed = get_dumps(our_status="failed")
    assert len(failed) == 0, f"Some downloads failed: {failed}"

    # 6. Wait for IA uploads
    wait_for_all_uploads(timeout=600)  # 10 minutes

    # 7. Wait for torrent creation
    wait_for_job_completion(job_type="create_torrent", timeout=120)

    # 8. Verify torrent created
    torrents = get_torrents(cycle_date="2026-01-20")
    assert len(torrents) > 0, "No torrent created"

    # 9. Verify manifest published
    wait_for_job_completion(job_type="publish_manifest", timeout=60)

    # 10. Cleanup
    cleanup_test_data()
```

### Test Coverage

**Target**: 80% line coverage

**Check coverage**:
```bash
# Generate HTML coverage report
pytest --cov=src --cov-report=html

# Open report
open htmlcov/index.html
```

**Coverage configuration** (`.coveragerc` or `pyproject.toml`):

```ini
# .coveragerc
[run]
source = src
omit =
    */tests/*
    */venv/*
    */__pycache__/*

[report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise AssertionError
    raise NotImplementedError
    if __name__ == .__main__.:
    if TYPE_CHECKING:
```

### Continuous Integration

**GitHub Actions** (`.github/workflows/ci.yml`):

```yaml
name: CI

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          pip install --upgrade pip
          pip install -r requirements.txt
          pip install -r requirements-dev.txt

      - name: Lint with ruff
        run: ruff check src/ tests/

      - name: Type check with mypy
        run: mypy src/

      - name: Format check with black
        run: black --check src/ tests/

      - name: Run tests with coverage
        run: pytest --cov=src --cov-report=xml --cov-report=term

      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage.xml
          fail_ci_if_error: true

  integration:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build containers
        run: docker compose -f docker-compose.dev.yml build

      - name: Run integration tests
        run: |
          docker compose -f docker-compose.dev.yml up -d
          sleep 10
          docker compose -f docker-compose.dev.yml exec -T controller pytest tests/test_integration/
          docker compose -f docker-compose.dev.yml down
```

---

## Code Quality

### Code Formatting: Black

**Configuration** (`pyproject.toml`):

```toml
[tool.black]
line-length = 100
target-version = ['py312']
include = '\.pyi?$'
```

**Usage**:
```bash
# Format all code
black src/ tests/

# Check without modifying
black --check src/ tests/

# Format specific file
black src/scraper/scraper.py
```

### Linting: Ruff

**Configuration** (`pyproject.toml`):

```toml
[tool.ruff]
line-length = 100
target-version = "py312"

select = [
    "E",   # pycodestyle errors
    "W",   # pycodestyle warnings
    "F",   # pyflakes
    "I",   # isort
    "B",   # flake8-bugbear
    "C4",  # flake8-comprehensions
    "UP",  # pyupgrade
]

ignore = [
    "E501",  # line too long (handled by black)
]

[tool.ruff.per-file-ignores]
"__init__.py" = ["F401"]  # Allow unused imports in __init__.py
```

**Usage**:
```bash
# Check all code
ruff check src/ tests/

# Auto-fix issues
ruff check --fix src/ tests/

# Check specific file
ruff check src/scraper/scraper.py
```

### Type Checking: Mypy

**Configuration** (`pyproject.toml`):

```toml
[tool.mypy]
python_version = "3.12"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
no_implicit_optional = true

[[tool.mypy.overrides]]
module = "tests.*"
disallow_untyped_defs = false
```

**Usage**:
```bash
# Type check all code
mypy src/

# Check specific module
mypy src/scraper/

# Show error codes
mypy --show-error-codes src/
```

**Type hint examples**:

```python
from typing import Optional, Dict, List, Any
from pathlib import Path
import sqlite3

def download_dump(
    url: str,
    destination: Path,
    expected_md5: str,
    max_retries: int = 5
) -> bool:
    """Download dump file with retry logic.

    Args:
        url: Download URL
        destination: Local file path
        expected_md5: Expected MD5 hash
        max_retries: Maximum retry attempts

    Returns:
        True if successful, False otherwise
    """
    ...

def get_dumps(
    conn: sqlite3.Connection,
    cycle_date: str,
    status: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Fetch dumps from database.

    Args:
        conn: Database connection
        cycle_date: Cycle date (YYYY-MM-DD)
        status: Filter by status (optional)

    Returns:
        List of dump dictionaries
    """
    ...
```

### Pre-commit Hooks

**Configuration** (`.pre-commit-config.yaml`):

```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 24.1.1
    hooks:
      - id: black
        language_version: python3.12

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.11
    hooks:
      - id: ruff
        args: [--fix]

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        additional_dependencies: [types-requests]

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
        args: ['--maxkb=1000']
      - id: check-merge-conflict
```

**Usage**:
```bash
# Install hooks
pre-commit install

# Run manually on all files
pre-commit run --all-files

# Run on staged files (happens automatically on commit)
pre-commit run

# Update hooks to latest versions
pre-commit autoupdate
```

---

## Debugging

### Remote Debugging with debugpy

Add to container in `docker-compose.dev.yml`:

```yaml
scraper:
  # ... other config
  ports:
    - "5678:5678"  # debugpy port
  command: python -m debugpy --listen 0.0.0.0:5678 --wait-for-client /app/src/scraper/scraper.py
```

**VS Code launch.json**:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Attach to Scraper",
      "type": "python",
      "request": "attach",
      "connect": {
        "host": "localhost",
        "port": 5678
      },
      "pathMappings": [
        {
          "localRoot": "${workspaceFolder}/src",
          "remoteRoot": "/app/src"
        }
      ]
    }
  ]
}
```

### Logging

**Standard logging setup** (`src/common/logging.py`):

```python
import logging
import sys

def setup_logging(level: str = "INFO") -> None:
    """Configure logging for WikiSeed components."""

    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout
    )

# Usage in each module
import logging
from common.logging import setup_logging

setup_logging(level="DEBUG")
logger = logging.getLogger(__name__)

logger.info("Starting scraper")
logger.debug(f"Processing dump: {dump_id}")
logger.error(f"Download failed: {error}")
```

### Common Debugging Tasks

```bash
# Check database contents
docker compose exec controller sqlite3 /data/db/jobs.db "SELECT * FROM jobs LIMIT 10;"

# Tail container logs
docker compose logs -f scraper

# Execute shell in container
docker compose exec scraper /bin/bash

# Run Python REPL in container
docker compose exec controller python

# Check environment variables
docker compose exec controller env | grep IA_
```

---

## Contributing

WikiSeed is an open-source project and welcomes contributions! This section covers how to contribute effectively.

### Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork**:
   ```bash
   git clone https://github.com/YOUR_USERNAME/wikiseed-server.git
   cd wikiseed-server
   ```
3. **Add upstream remote**:
   ```bash
   git remote add upstream https://github.com/ORIGINAL_OWNER/wikiseed-server.git
   ```
4. **Set up development environment**:
   ```bash
   make install
   ```

### Branch Naming

Use descriptive branch names:

- **Features**: `feature/add-torrent-stats`
- **Bug fixes**: `fix/database-locking-issue`
- **Documentation**: `docs/update-deployment-guide`
- **Refactoring**: `refactor/simplify-retry-logic`

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, no logic change)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

**Examples**:
```
feat(scraper): add archive.today integration

Scraper now archives dump index pages to archive.today during
discovery. Archive URLs stored in dumps.archive_today_url.

Closes #42
```

```
fix(downloader): handle HTTP 429 rate limiting

Added exponential backoff for rate limit responses. Retry after
delay specified in Retry-After header.
```

```
docs(architecture): document job queue locking

Added section explaining SQLite BEGIN IMMEDIATE locking strategy
for preventing race conditions in job queue.
```

### Pull Request Process

1. **Create feature branch**:
   ```bash
   git checkout -b feature/your-feature
   ```

2. **Make changes** and commit:
   ```bash
   git add .
   git commit -m "feat(component): description"
   ```

3. **Keep branch updated**:
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

4. **Run tests and linters**:
   ```bash
   make lint
   make test
   ```

5. **Push to your fork**:
   ```bash
   git push origin feature/your-feature
   ```

6. **Open Pull Request** on GitHub:
   - Use descriptive title and description
   - Reference related issues (e.g., "Closes #42")
   - Add screenshots/examples if relevant
   - Mark as draft if work-in-progress

### Code Review Guidelines

**For Contributors**:
- Respond to review comments promptly
- Make requested changes in new commits (don't force-push)
- Mark conversations as resolved after addressing
- Be open to feedback and suggestions

**For Reviewers**:
- Be respectful and constructive
- Explain the "why" behind suggestions
- Approve when ready, request changes if needed
- Test changes locally when possible

### Testing Requirements

All PRs must:
- ✅ Pass CI/CD pipeline (linting, type checking, tests)
- ✅ Maintain or improve test coverage (target: 80%)
- ✅ Include tests for new features
- ✅ Include tests for bug fixes (regression tests)

### Documentation Requirements

Update documentation when:
- Adding new features → Update relevant .md files
- Changing APIs → Update API.md
- Modifying database → Update DATABASE.md
- Changing deployment → Update DEPLOYMENT.md

### What to Contribute

**Good First Issues**:
- Documentation improvements
- Adding tests
- Fixing typos
- Small bug fixes

**Larger Contributions**:
- New features (discuss in issue first!)
- Performance improvements
- Major refactoring
- New integrations

**Always welcome**:
- Bug reports (with reproduction steps)
- Feature requests (with use cases)
- Documentation improvements
- Test coverage improvements

### Getting Help

- **Questions**: Open a GitHub Discussion
- **Bugs**: Open a GitHub Issue
- **Security issues**: Email security@wikiseed.app (private)

---

## Development Tips

### Faster Development Iteration

1. **Use small wiki mode** for quick end-to-end validation
2. **Run single containers** instead of full stack:
   ```bash
   docker compose -f docker-compose.dev.yml up scraper
   ```
3. **Use database browser** to inspect state without SQL
4. **Set LOG_LEVEL=DEBUG** for verbose output
5. **Use pytest -x** to stop on first failure

### Common Pitfalls

1. **SQLite locking**: Don't hold transactions open long
2. **Docker volume permissions**: Match host UID/GID
3. **Time zones**: Always use UTC for timestamps
4. **File paths**: Use pathlib.Path, not string concatenation
5. **JSON in SQLite**: Use `json.dumps()` for TEXT columns

### Useful Tools

- **sqlite-web**: Web-based SQLite browser
- **ipython**: Better Python REPL
- **httpie**: Better curl for API testing
- **jq**: JSON processor for command line
- **watch**: Monitor command output in real-time

### Performance Testing

```bash
# Time how long discovery takes
time docker compose exec controller python -c "from src.scraper.scraper import discover; discover('2026-01-20')"

# Profile Python code
python -m cProfile -o profile.stats src/scraper/scraper.py
python -m pstats profile.stats
```

---

## Related Documentation

- [bigpicture.md](bigpicture.md): Project overview and strategy
- [ARCHITECTURE.md](ARCHITECTURE.md): Container architecture and design
- [DATABASE.md](DATABASE.md): Database schema and queries
- [DEPLOYMENT.md](DEPLOYMENT.md): Production deployment guide
- [API.md](API.md): Monitor web UI and REST API reference (future)
