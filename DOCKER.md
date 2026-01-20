# WikiSeed Docker Setup Guide

This guide covers the Docker setup for WikiSeed Server.

## Architecture

WikiSeed runs **8 Docker containers** orchestrated by Docker Compose:

1. **controller** - Central orchestration and job scheduling
2. **scraper** - Discovers dumps from Wikimedia
3. **downloader** - Downloads dump files
4. **uploader** - Uploads to Internet Archive
5. **creator** - Creates torrents and metadata
6. **publisher** - Publishes to R2, Gist, pastebin
7. **seeder** - qBittorrent for torrent seeding
8. **monitor** - Web UI and REST API

Plus a one-time **db-init** container for database initialization.

## Prerequisites

- Docker Engine 24.0+
- Docker Compose v2
- 2TB+ available disk space
- 8GB+ RAM (16GB recommended)

## Quick Start

### 1. Create Required Directories

```bash
mkdir -p data/{db,dumps,torrents,seeder/{config,watch}}
mkdir -p logs
```

### 2. Create Configuration Files

```bash
# Copy example files
cp config.example.yaml config.yaml
cp .env.example .env

# Edit with your settings
nano config.yaml
nano .env
```

### 3. Initialize Database

```bash
# Run database initialization
docker compose run --rm db-init

# Verify database was created
ls -lh data/db/jobs.db
```

### 4. Start Services

```bash
# Start all services
docker compose up -d

# Check status
docker compose ps

# View logs
docker compose logs -f

# View logs for specific service
docker compose logs -f controller
```

### 5. Access Services

- **Monitor Web UI**: http://localhost:8000
- **qBittorrent Web UI**: http://localhost:8080 (default login: admin/adminadmin)

## Development Setup

For development with live code reloading:

```bash
# Start with development override
docker compose -f docker-compose.yml -f docker-compose.dev.yml up

# Or using make
make dev-up
```

The development setup:
- Mounts source code as read-only volumes for live updates
- Sets `LOG_LEVEL=DEBUG`
- Enables Flask debug mode for Monitor
- Uses Python's `-m` module execution for better error messages

## Container Management

### View Running Containers

```bash
docker compose ps
```

### Start/Stop Services

```bash
# Stop all services
docker compose down

# Stop specific service
docker compose stop controller

# Start specific service
docker compose start controller

# Restart service
docker compose restart controller
```

### View Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f scraper

# Last 100 lines
docker compose logs --tail=100 downloader

# Since timestamp
docker compose logs --since 2026-01-19T10:00:00 uploader
```

### Execute Commands in Containers

```bash
# Open shell in controller
docker compose exec controller /bin/bash

# Run Python command
docker compose exec controller python -c "import sys; print(sys.version)"

# Check database
docker compose exec controller sqlite3 /data/db/jobs.db "SELECT COUNT(*) FROM jobs;"
```

## Building Images

### Build All Images

```bash
docker compose build
```

### Build Specific Service

```bash
docker compose build controller
```

### Build Without Cache

```bash
docker compose build --no-cache
```

### Pull Latest Base Images

```bash
docker compose pull
```

## Data Persistence

All data is stored in bind-mounted volumes in the `./data` directory:

- `./data/db/` - SQLite database
- `./data/dumps/` - Downloaded dump files
- `./data/torrents/` - Created torrents and metadata
- `./data/seeder/config/` - qBittorrent configuration
- `./data/seeder/watch/` - Directory for new .torrent files

These directories are automatically mounted by docker-compose.yml.

## Environment Variables

Required environment variables in `.env`:

```bash
# Internet Archive
IA_ACCESS=your_ia_access_key
IA_SECRET=your_ia_secret_key

# Cloudflare R2
R2_ACCOUNT_ID=your_account_id
R2_ACCESS_KEY_ID=your_access_key
R2_SECRET_ACCESS_KEY=your_secret_key

# GitHub Gist
GIST_TOKEN=your_github_token

# pastebin.com
PASTEBIN_API_KEY=your_api_key

# SMTP (for alerts)
SMTP_USERNAME=your_smtp_user
SMTP_PASSWORD=your_smtp_password

# Optional
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL
```

## Networking

All containers run on a private bridge network `wikiseed-net`. Only the following ports are exposed to the host:

- `8000` - Monitor Web UI (localhost only)
- `8080` - qBittorrent Web UI (localhost only)
- `6881` - BitTorrent port (TCP/UDP, public)

For remote access to web UIs, use SSH tunneling:

```bash
ssh -L 8000:localhost:8000 -L 8080:localhost:8080 user@your-server
```

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker compose logs controller

# Rebuild container
docker compose build controller
docker compose up -d controller
```

### Database Locked

```bash
# Stop all services
docker compose down

# Check for stale lock
ls -la data/db/

# Restart services
docker compose up -d
```

### Disk Space Issues

```bash
# Check disk usage
df -h

# Clean up Docker system
docker system prune -a -f

# Remove old images
docker image prune -a -f
```

### Permission Issues

```bash
# Fix data directory permissions
sudo chown -R 1000:1000 data/

# Or match your user
sudo chown -R $(id -u):$(id -g) data/
```

### View Container Resource Usage

```bash
docker stats
```

## Updates and Maintenance

### Update to Latest Version

```bash
# Pull latest code
git pull

# Rebuild containers
docker compose build

# Restart services
docker compose down
docker compose up -d
```

### Backup Database

```bash
# Stop services first
docker compose down

# Backup database
cp data/db/jobs.db backups/jobs-$(date +%Y-%m-%d).db

# Restart services
docker compose up -d
```

### Reset Everything

```bash
# WARNING: This deletes all data!

# Stop and remove containers
docker compose down -v

# Remove data
rm -rf data/

# Start fresh
mkdir -p data/{db,dumps,torrents,seeder/{config,watch}}
docker compose run --rm db-init
docker compose up -d
```

## Production Deployment

For production deployment, consider:

1. **Bind Monitor and qBittorrent Web UIs to localhost only** (already configured)
2. **Use SSH tunneling for remote access**
3. **Set up automated backups** (see [DEPLOYMENT.md](docs/DEPLOYMENT.md))
4. **Configure log rotation**
5. **Monitor disk space**
6. **Set resource limits in docker-compose.yml**:

```yaml
services:
  downloader:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G
```

## Next Steps

- Review [ARCHITECTURE.md](docs/ARCHITECTURE.md) for system design
- See [DEVELOPMENT.md](docs/DEVELOPMENT.md) for contribution guide
- Check [DEPLOYMENT.md](docs/DEPLOYMENT.md) for production deployment

## Getting Help

- GitHub Issues: https://github.com/yourusername/wikiseed-server/issues
- Documentation: [docs/](docs/)
