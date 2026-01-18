# WikiSeed: Deployment Guide

## Overview

This guide covers production deployment of WikiSeed on a single server using Docker Compose. It assumes you have a basic Ubuntu/Debian server with Docker installed.

## Prerequisites

- **Server**: Ubuntu 22.04+ or Debian 11+ (physical server, VM, or VPS)
- **Docker**: Docker Engine 24.0+ and Docker Compose v2
- **Storage**: Minimum 2TB available (adjust based on your needs)
- **RAM**: Minimum 8GB (16GB+ recommended)
- **Network**: Stable internet connection with sufficient bandwidth

### Installing Docker (if needed)

```bash
# Update package list
sudo apt update

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add your user to docker group
sudo usermod -aG docker $USER
newgrp docker

# Verify installation
docker --version
docker compose version
```

---

## Installation

### 1. Clone Repository

```bash
# Create application directory
sudo mkdir -p /opt/wikiseed
sudo chown $USER:$USER /opt/wikiseed
cd /opt/wikiseed

# Clone repository
git clone https://github.com/yourusername/wikiseed-server.git .

# Checkout specific version (recommended for production)
git checkout v1.0.0  # Replace with actual release tag
```

### 2. Create Data Directories

```bash
# Create all required directories
mkdir -p data/{db,dumps,torrents,seeder/{config,watch}}
mkdir -p logs
mkdir -p backups/db

# Set permissions
chmod 755 data
chmod 700 data/db
chmod 755 data/dumps data/torrents
```

### 3. Configure System

#### Create config.yaml

```bash
# Copy example configuration
cp config.example.yaml config.yaml

# Edit configuration
nano config.yaml
```

**Key settings to adjust**:
```yaml
wikiseed:
  storage:
    dumps_path: /data/dumps
    torrents_path: /data/torrents
    max_storage_gb: 2000          # Adjust based on available disk space
    cleanup_threshold_pct: 85

  download:
    bandwidth_limit_mbps: 0       # 0 = unlimited, set if needed

  monitoring:
    web_ui_enabled: true
    web_ui_port: 8000

  alerts:
    email:
      enabled: true
      smtp_host: smtp.gmail.com
      smtp_port: 587
      from: alerts@wikiseed.app
      to: your-email@example.com  # Change this!
```

#### Create .env File

```bash
# Copy example .env
cp .env.example .env

# Set restrictive permissions
chmod 600 .env

# Edit with your credentials
nano .env
```

**Required secrets**:
```bash
# .env

# Internet Archive
IA_ACCESS=your_ia_access_key_here
IA_SECRET=your_ia_secret_key_here

# Cloudflare R2
R2_ACCOUNT_ID=your_r2_account_id
R2_ACCESS_KEY_ID=your_r2_access_key
R2_SECRET_ACCESS_KEY=your_r2_secret_key

# GitHub Gist
GIST_TOKEN=your_github_personal_access_token

# pastebin.com
PASTEBIN_API_KEY=your_pastebin_api_key

# archive.today (if API key required)
ARCHIVE_TODAY_API_KEY=your_archive_today_key

# Academic Torrents (optional)
ACADEMIC_TORRENTS_API_KEY=your_academic_torrents_key

# SMTP for email alerts
SMTP_USERNAME=your_smtp_username
SMTP_PASSWORD=your_smtp_password
```

**Obtaining Credentials**:

- **Internet Archive**: https://archive.org/account/s3.php
- **Cloudflare R2**: Cloudflare dashboard → R2 → Manage R2 API Tokens
- **GitHub Gist**: https://github.com/settings/tokens (needs `gist` scope)
- **pastebin.com**: https://pastebin.com/doc_api (requires pro account)
- **SMTP**: Use Gmail app password or dedicated SMTP service

### 4. Initialize Database

```bash
# Run database initialization
docker compose run --rm controller python /app/scripts/init_db.py

# Verify database created
ls -lh data/db/jobs.db
sqlite3 data/db/jobs.db "SELECT * FROM system_state;"
```

### 5. Start Services

```bash
# Start all containers
docker compose up -d

# Verify containers are running
docker compose ps

# Check logs
docker compose logs -f
```

Expected output:
```
NAME                    STATUS              PORTS
wikiseed-controller     running
wikiseed-scraper        running
wikiseed-downloader     running
wikiseed-uploader       running
wikiseed-creator        running
wikiseed-publisher      running
wikiseed-seeder         running             0.0.0.0:6881->6881/tcp
wikiseed-monitor        running             127.0.0.1:8000->8000/tcp
```

### 6. Verify Installation

```bash
# Check monitor web UI (if enabled)
curl http://localhost:8000

# Check database
docker compose exec controller sqlite3 /data/db/jobs.db "SELECT key, value FROM system_state;"

# Check qBittorrent web UI
# Open browser: http://your-server-ip:8080
# Default credentials: admin / adminadmin (change immediately!)
```

---

## System Service (Auto-Start on Boot)

Create a systemd service to automatically start WikiSeed on boot.

### Create Service File

```bash
sudo nano /etc/systemd/system/wikiseed.service
```

**Service configuration**:
```ini
[Unit]
Description=WikiSeed Wikimedia Dump Archival System
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/wikiseed
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
```

### Enable and Start Service

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service (start on boot)
sudo systemctl enable wikiseed.service

# Start service now
sudo systemctl start wikiseed.service

# Check status
sudo systemctl status wikiseed.service

# View logs
sudo journalctl -u wikiseed.service -f
```

---

## Backups

### Database Backups

**Automated backup script**:

```bash
# Create backup script
sudo nano /usr/local/bin/wikiseed-backup-db.sh
```

```bash
#!/bin/bash
# wikiseed-backup-db.sh

set -e

# Configuration
BACKUP_DIR="/opt/wikiseed/backups/db"
DB_PATH="/opt/wikiseed/data/db/jobs.db"
DATE=$(date +%Y-%m-%d)
TIMESTAMP=$(date +%Y-%m-%d_%H-%M-%S)

# Ensure backup directory exists
mkdir -p "$BACKUP_DIR"

# Create backup using SQLite backup API
echo "Creating database backup: jobs-${TIMESTAMP}.db"
sqlite3 "$DB_PATH" ".backup ${BACKUP_DIR}/jobs-${TIMESTAMP}.db"

# Compress backup
echo "Compressing backup..."
gzip "${BACKUP_DIR}/jobs-${TIMESTAMP}.db"

# Upload to cloud storage (Backblaze B2)
echo "Uploading to cloud storage..."
# Install rclone first: sudo apt install rclone
# Configure rclone: rclone config (set up B2 remote named 'b2')
rclone copy "${BACKUP_DIR}/jobs-${TIMESTAMP}.db.gz" b2:wikiseed-backups/db/

# Retention: Keep 7 daily, 4 weekly (Sundays), 12 monthly (1st of month)
echo "Cleaning up old local backups..."

# Keep all backups from last 7 days
# Keep Sunday backups (weekly) for last 4 weeks
# Keep 1st of month backups (monthly) for last 12 months
# Delete everything else older than 7 days

find "$BACKUP_DIR" -name "jobs-*.db.gz" -mtime +7 \
    ! -name "jobs-*-01_*.db.gz" \
    ! -name "jobs-*-08_*.db.gz" \
    ! -name "jobs-*-15_*.db.gz" \
    ! -name "jobs-*-22_*.db.gz" \
    ! -name "jobs-*-29_*.db.gz" \
    -delete

# Delete monthly backups older than 12 months
find "$BACKUP_DIR" -name "jobs-*-01_*.db.gz" -mtime +365 -delete

echo "Backup completed successfully: jobs-${TIMESTAMP}.db.gz"
echo "Local: ${BACKUP_DIR}/jobs-${TIMESTAMP}.db.gz"
echo "Cloud: b2:wikiseed-backups/db/jobs-${TIMESTAMP}.db.gz"
```

**Make script executable**:
```bash
sudo chmod +x /usr/local/bin/wikiseed-backup-db.sh

# Test backup
sudo /usr/local/bin/wikiseed-backup-db.sh
```

### Configure rclone for Cloud Backups

```bash
# Install rclone
sudo apt install rclone

# Configure Backblaze B2 (or your preferred cloud storage)
rclone config

# Follow prompts:
# n) New remote
# name> b2
# Storage> backblaze
# account> your_application_key_id
# key> your_application_key
# (accept other defaults)

# Test rclone
rclone ls b2:
```

### Schedule Automated Backups

```bash
# Edit crontab
sudo crontab -e

# Add daily backup at 2 AM
0 2 * * * /usr/local/bin/wikiseed-backup-db.sh >> /var/log/wikiseed-backup.log 2>&1
```

### Config and Secrets Backup

```bash
# Backup configuration files (store securely!)
sudo tar -czf /opt/wikiseed/backups/config-$(date +%Y-%m-%d).tar.gz \
    /opt/wikiseed/config.yaml \
    /opt/wikiseed/.env

# Upload to cloud (encrypted!)
rclone copy /opt/wikiseed/backups/config-$(date +%Y-%m-%d).tar.gz \
    b2:wikiseed-backups/config/ \
    --b2-chunk-size 96M
```

### Restore from Backup

```bash
# Stop WikiSeed
sudo systemctl stop wikiseed.service

# Download backup from cloud
rclone copy b2:wikiseed-backups/db/jobs-2026-01-18_02-00-00.db.gz /tmp/

# Restore database
gunzip -c /tmp/jobs-2026-01-18_02-00-00.db.gz > /opt/wikiseed/data/db/jobs.db

# Verify restoration
sqlite3 /opt/wikiseed/data/db/jobs.db "SELECT value FROM system_state WHERE key = 'schema_version';"

# Restart WikiSeed
sudo systemctl start wikiseed.service

# Verify system health
docker compose ps
docker compose logs controller | tail -50
```

---

## Monitoring and Alerting

### Uptime Kuma Setup

Uptime Kuma is a self-hosted monitoring tool with a beautiful UI.

```bash
# Create Uptime Kuma directory
mkdir -p /opt/uptime-kuma

# Run Uptime Kuma container
docker run -d \
  --name uptime-kuma \
  --restart unless-stopped \
  -p 3001:3001 \
  -v /opt/uptime-kuma:/app/data \
  louislam/uptime-kuma:1
```

**Access Uptime Kuma**:
- URL: http://your-server-ip:3001
- Create admin account on first access

**Configure Monitors**:

1. **WikiSeed Monitor Web UI**
   - Type: HTTP(s)
   - URL: http://localhost:8000
   - Interval: 60 seconds

2. **qBittorrent Web UI**
   - Type: HTTP(s)
   - URL: http://localhost:8080
   - Interval: 60 seconds

3. **Docker Containers**
   - Type: Docker Container
   - Container Name: wikiseed-controller (repeat for each container)
   - Interval: 60 seconds

4. **Disk Space**
   - Type: Script
   - Script: `df -h /opt/wikiseed/data | awk 'NR==2 {print $5}' | sed 's/%//'`
   - Max: 85 (alert if >85% full)

**Configure Notifications**:
- Email, Telegram, Discord, Slack, etc.
- Set up in Settings → Notifications
- Apply to all monitors

### Email Alerts (Built-in)

WikiSeed controller sends email alerts for critical failures. Already configured in `config.yaml`:

```yaml
alerts:
  email:
    enabled: true
    smtp_host: smtp.gmail.com
    smtp_port: 587
    from: alerts@wikiseed.app
    to: your-email@example.com
```

**Test email alerts**:
```bash
# Trigger a test alert (if implemented)
docker compose exec controller python /app/scripts/test_alert.py
```

### Manual Health Checks

```bash
# Check all container status
docker compose ps

# Check database health
docker compose exec controller sqlite3 /data/db/jobs.db "PRAGMA integrity_check;"

# Check disk space
df -h /opt/wikiseed/data

# Check recent jobs
docker compose exec controller sqlite3 /data/db/jobs.db \
    "SELECT job_type, status, COUNT(*) as count
     FROM jobs
     WHERE created_at > datetime('now', '-24 hours')
     GROUP BY job_type, status;"

# Check failed jobs
docker compose exec controller sqlite3 /data/db/jobs.db \
    "SELECT id, job_type, last_error
     FROM jobs
     WHERE status = 'failed'
     ORDER BY created_at DESC
     LIMIT 10;"
```

---

## Log Management

### Container Logs

Logs are managed by Docker's json-file driver with automatic rotation (configured in `docker-compose.yml`):

```yaml
logging:
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "3"
```

**View logs**:
```bash
# All containers
docker compose logs -f

# Specific container
docker compose logs -f controller

# Last 100 lines
docker compose logs --tail=100 downloader

# Since timestamp
docker compose logs --since 2026-01-18T10:00:00
```

### Application Logs

If containers write logs to files (in `/data/logs`), configure logrotate:

```bash
# Create logrotate configuration
sudo nano /etc/logrotate.d/wikiseed
```

```
/opt/wikiseed/logs/*.log {
    daily
    rotate 90
    compress
    delaycompress
    missingok
    notifempty
    create 0644 $USER $USER
    postrotate
        docker compose -f /opt/wikiseed/docker-compose.yml restart 2>/dev/null || true
    endscript
}
```

**Test logrotate**:
```bash
sudo logrotate -f /etc/logrotate.d/wikiseed
```

---

## System Updates

### Automatic Security Updates

Enable unattended-upgrades for automatic security patches:

```bash
# Install unattended-upgrades
sudo apt install unattended-upgrades

# Enable automatic updates
sudo dpkg-reconfigure -plow unattended-upgrades

# Verify configuration
cat /etc/apt/apt.conf.d/50unattended-upgrades
```

**Configuration** (`/etc/apt/apt.conf.d/50unattended-upgrades`):
```
Unattended-Upgrade::Allowed-Origins {
    "${distro_id}:${distro_codename}-security";
};

Unattended-Upgrade::AutoFixInterruptedDpkg "true";
Unattended-Upgrade::MinimalSteps "true";
Unattended-Upgrade::Mail "your-email@example.com";
Unattended-Upgrade::Automatic-Reboot "false";
```

### WikiSeed Updates

**Manual update procedure**:

```bash
# Navigate to WikiSeed directory
cd /opt/wikiseed

# Check for updates
git fetch origin

# View changes
git log HEAD..origin/main --oneline

# Stop services
sudo systemctl stop wikiseed.service

# Backup database first!
/usr/local/bin/wikiseed-backup-db.sh

# Pull latest code
git pull origin main
# OR checkout specific version:
# git checkout v1.1.0

# Check for migration requirements
cat CHANGELOG.md  # Read release notes

# Run database migrations (if any)
docker compose run --rm controller python /app/scripts/init_db.py

# Rebuild containers (if needed)
docker compose build

# Start services
sudo systemctl start wikiseed.service

# Verify update
docker compose ps
docker compose logs -f controller | head -50

# Check schema version
docker compose exec controller sqlite3 /data/db/jobs.db \
    "SELECT value FROM system_state WHERE key = 'schema_version';"
```

### Docker Image Updates

```bash
# Pull latest base images
docker compose pull

# Rebuild containers
docker compose build --no-cache

# Restart with new images
docker compose up -d

# Clean up old images
docker image prune -f
```

---

## Rollback Procedure

If an update causes issues, rollback to previous version:

### 1. Identify Previous Version

```bash
# View git history
git log --oneline -10

# Or check deployed versions
git tag -l
```

### 2. Stop Services

```bash
sudo systemctl stop wikiseed.service
```

### 3. Restore Database Backup

```bash
# List available backups
ls -lh /opt/wikiseed/backups/db/
rclone ls b2:wikiseed-backups/db/

# Download from cloud (if needed)
rclone copy b2:wikiseed-backups/db/jobs-2026-01-17_02-00-00.db.gz /tmp/

# Restore database
gunzip -c /tmp/jobs-2026-01-17_02-00-00.db.gz > /opt/wikiseed/data/db/jobs.db
```

### 4. Checkout Previous Code Version

```bash
cd /opt/wikiseed

# Rollback to previous version
git checkout v1.0.0  # Replace with actual previous version

# OR rollback to specific commit
git checkout abc123def
```

### 5. Rebuild and Restart

```bash
# Rebuild containers (if Dockerfile changed)
docker compose build

# Start services
sudo systemctl start wikiseed.service
```

### 6. Verify Rollback

```bash
# Check containers
docker compose ps

# Check logs for errors
docker compose logs -f

# Verify database schema
docker compose exec controller sqlite3 /data/db/jobs.db \
    "SELECT value FROM system_state WHERE key = 'schema_version';"

# Check system health
curl http://localhost:8000
```

### 7. Document Incident

```bash
# Create incident report
cat > /opt/wikiseed/incidents/$(date +%Y-%m-%d)-rollback.md << EOF
# Rollback Incident - $(date +%Y-%m-%d)

## Issue
[Describe what went wrong with the update]

## Rollback Actions
- Stopped services at: $(date)
- Restored DB from: jobs-2026-01-17_02-00-00.db.gz
- Rolled back code to: v1.0.0
- Restarted services at: $(date)

## Resolution
[Describe current state and next steps]

## Prevention
[What to do differently next time]
EOF
```

---

## Firewall Configuration

Configure firewall to secure your server:

```bash
# Install ufw (if not installed)
sudo apt install ufw

# Allow SSH
sudo ufw allow ssh

# Allow BitTorrent port
sudo ufw allow 6881/tcp
sudo ufw allow 6881/udp

# If accessing monitor/qBittorrent UI remotely:
# sudo ufw allow from YOUR_IP_ADDRESS to any port 8000
# sudo ufw allow from YOUR_IP_ADDRESS to any port 8080

# Enable firewall
sudo ufw enable

# Verify rules
sudo ufw status verbose
```

**Recommended**: Access web UIs via SSH tunnel instead of opening ports:

```bash
# From your local machine
ssh -L 8000:localhost:8000 -L 8080:localhost:8080 user@wikiseed-server

# Then access locally:
# http://localhost:8000 (monitor UI)
# http://localhost:8080 (qBittorrent UI)
```

---

## Performance Tuning

### Disk I/O Optimization

```bash
# If using SSD, enable TRIM
sudo systemctl enable fstab-trim.timer

# Monitor disk I/O
iostat -x 5
```

### Docker Performance

```bash
# Configure Docker daemon
sudo nano /etc/docker/daemon.json
```

```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  },
  "storage-driver": "overlay2",
  "default-address-pools": [
    {
      "base": "172.80.0.0/16",
      "size": 24
    }
  ]
}
```

```bash
# Restart Docker
sudo systemctl restart docker
```

### SQLite Performance

Database is already configured with optimal settings in code, but you can verify:

```bash
docker compose exec controller sqlite3 /data/db/jobs.db "PRAGMA journal_mode;"
# Should return: wal

docker compose exec controller sqlite3 /data/db/jobs.db "PRAGMA synchronous;"
# Should return: 1 (NORMAL)
```

---

## Troubleshooting

### Containers Won't Start

```bash
# Check logs
docker compose logs

# Check disk space
df -h

# Check Docker daemon
sudo systemctl status docker

# Rebuild containers
docker compose down
docker compose build --no-cache
docker compose up -d
```

### Database Locked Errors

```bash
# Check for stuck processes
fuser /opt/wikiseed/data/db/jobs.db

# If stuck, stop all containers
docker compose down

# Wait for WAL checkpoint
sleep 10

# Restart
docker compose up -d
```

### Disk Full

```bash
# Check disk usage
df -h
du -sh /opt/wikiseed/data/*

# Clean up old Docker images
docker image prune -a -f

# Clean up old dumps (if storage full)
# Manually delete oldest cycle dumps from /opt/wikiseed/data/dumps/

# Adjust cleanup threshold in config.yaml
nano /opt/wikiseed/config.yaml
# Lower cleanup_threshold_pct from 85% to 75%

# Restart to apply config
docker compose restart controller
```

### Jobs Not Processing

```bash
# Check job queue
docker compose exec controller sqlite3 /data/db/jobs.db \
    "SELECT job_type, status, COUNT(*) FROM jobs GROUP BY job_type, status;"

# Check for failed jobs
docker compose exec controller sqlite3 /data/db/jobs.db \
    "SELECT id, job_type, last_error FROM jobs WHERE status = 'failed';"

# Check worker container logs
docker compose logs scraper
docker compose logs downloader
docker compose logs uploader

# Restart stuck containers
docker compose restart scraper downloader uploader
```

### Network Issues

```bash
# Test Wikimedia connectivity
curl -I https://dumps.wikimedia.org

# Test Internet Archive
curl -I https://archive.org

# Check DNS
nslookup dumps.wikimedia.org

# Check Docker network
docker network inspect wikiseed_default
```

---

## Security Best Practices

### File Permissions

```bash
# Ensure proper ownership
sudo chown -R $USER:$USER /opt/wikiseed

# Secure sensitive files
chmod 600 /opt/wikiseed/.env
chmod 600 /opt/wikiseed/data/db/jobs.db
chmod 700 /opt/wikiseed/data/db
```

### SSH Hardening (Optional)

```bash
# Disable password authentication
sudo nano /etc/ssh/sshd_config
```

```
PasswordAuthentication no
PermitRootLogin no
```

```bash
# Restart SSH
sudo systemctl restart sshd
```

### Regular Security Updates

```bash
# Check for available updates
sudo apt update
sudo apt list --upgradable

# Apply updates (during maintenance window)
sudo apt upgrade -y

# Reboot if kernel updated
sudo reboot
```

---

## Maintenance Checklist

### Daily
- [ ] Check Uptime Kuma dashboard for alerts
- [ ] Review email alerts (if any)

### Weekly
- [ ] Check disk space: `df -h`
- [ ] Review failed jobs: Check monitor UI or database
- [ ] Verify backups uploaded to cloud: `rclone ls b2:wikiseed-backups/db/ | tail`

### Monthly
- [ ] Review torrent seeding stats
- [ ] Check for WikiSeed updates: `git fetch && git log HEAD..origin/main`
- [ ] Review and clean up logs if needed
- [ ] Test backup restoration (quarterly)

### Quarterly
- [ ] Test rollback procedure with non-production backup
- [ ] Review and update documentation
- [ ] Review storage usage trends
- [ ] Plan capacity upgrades if needed

---

## Capacity Planning

### Storage Growth Estimates

Approximate storage requirements per cycle:

- **Compressed dumps**: ~800GB per complete cycle (all wikis, all languages)
- **Uncompressed dumps**: ~3TB per complete cycle (if enabled)
- **History dumps**: ~5TB per 1st cycle (if enabled)
- **Torrents**: Minimal (hard links to dump files)
- **Database**: ~500MB after 1 year, ~2GB after 5 years

**Recommended Storage**:
- **Minimal setup** (compressed only, 2 cycles): 2TB
- **Standard setup** (compressed + uncompressed, 4 cycles): 8TB
- **Full setup** (compressed + uncompressed + history): 20TB+

### Bandwidth Estimates

- **Download from Wikimedia**: ~1TB per cycle (compressed only)
- **Upload to Internet Archive**: ~1TB per cycle
- **Torrent seeding**: Variable (depends on swarm demand)

**Recommended Bandwidth**: 100 Mbps or better

### Scaling Triggers

Consider adding capacity when:
- Disk usage consistently >75%
- Download bandwidth saturated during cycle processing
- Job queue depth >500 jobs
- Processing can't complete before next cycle starts

---

## Related Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md): Container architecture and design
- [DATABASE.md](DATABASE.md): Database schema and queries
- [DEVELOPMENT.md](DEVELOPMENT.md): Development environment setup
- [bigpicture.md](bigpicture.md): Project overview and strategy
