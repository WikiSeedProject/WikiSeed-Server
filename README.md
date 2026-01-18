# WikiSeed Server

**Ensuring "at least one copy of everything" from all Wikimedia projects and languages.**

WikiSeed archives Wikimedia database dumps and distributes them via torrents and Internet Archive, with a focus on smaller language communities often overlooked by other backup projects.

---

## Quick Links

- **[Project Overview](docs/bigpicture.md)** - Mission, architecture overview, and strategy
- **[Architecture](docs/ARCHITECTURE.md)** - Technical architecture and container design
- **[Database](docs/DATABASE.md)** - Database schema and migrations
- **[Deployment](docs/DEPLOYMENT.md)** - Production deployment guide
- **[Development](docs/DEVELOPMENT.md)** - Development setup and contribution guide
- **[API Reference](docs/API.md)** - Monitor web UI and REST API documentation

---

## What is WikiSeed?

WikiSeed is an automated system that:

1. **Discovers** all available Wikimedia dumps (Wikipedia, Wiktionary, Wikisource, etc.)
2. **Downloads** dumps from Wikimedia servers
3. **Uploads** to Internet Archive for permanent storage and webseeding
4. **Creates** torrents bundling dumps by cycle date (1st and 20th of each month)
5. **Publishes** torrents and manifests to multiple channels (R2, Gist, pastebin, Academic Torrents)
6. **Seeds** torrents indefinitely to ensure availability

### Why WikiSeed?

- **Comprehensive**: Covers all Wikimedia projects and all languages
- **Resilient**: Multiple distribution channels (torrent, IA, Wikimedia mirrors)
- **Accessible**: Simple manifest API for automated consumption
- **Community-focused**: Prioritizes small language communities
- **Open**: AGPL-licensed server code, GPL-licensed client tools

---

## Features

### Server (This Repository)

- **Automated pipeline**: Discover → Download → Upload → Create Torrent → Publish
- **Containerized architecture**: 7 Docker containers coordinated via job queue
- **Resilient downloads**: Resumable downloads with exponential backoff retry
- **Torrent webseeds**: Internet Archive URLs + Wikimedia mirrors
- **Metadata generation**: HASH.json, STATUS.json, README.txt in every torrent
- **Archive preservation**: Dump pages archived to archive.today
- **Web monitoring UI**: Real-time job status and system health dashboard
- **REST API**: Programmatic access to jobs, dumps, and torrents

### Distribution

- **BitTorrent**: Primary distribution with public trackers
- **Internet Archive**: Permanent storage and webseed source
- **Cloudflare R2**: Manifest and .torrent file hosting
- **GitHub Gist**: Manifest backup
- **pastebin.com**: Manifest backup
- **Academic Torrents**: Auto-upload (optional)

---

## Architecture Overview

```
┌─────────────┐     ┌──────────────┐
│ Controller  │────▶│   SQLite DB  │
│ (schedules) │     │  (jobs.db)   │
└─────────────┘     └──────────────┘
                           │
       ┌───────────────────┼───────────────────┐
       │                   │                   │
       ▼                   ▼                   ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Scraper    │     │ Downloader  │     │  Uploader   │
│ (discovers) │     │ (fetches)   │     │ (to IA)     │
└─────────────┘     └─────────────┘     └─────────────┘
                           │                   │
                           └─────────┬─────────┘
                                     ▼
                              ┌─────────────┐
                              │  Creator    │
                              │ (torrents)  │
                              └─────────────┘
                                     │
                      ┌──────────────┼──────────────┐
                      ▼              ▼              ▼
               ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
               │ Publisher   │ │   Seeder    │ │  Monitor    │
               │ (R2, Gist)  │ │(qBittorrent)│ │  (web UI)   │
               └─────────────┘ └─────────────┘ └─────────────┘
```

**Components**:
- **Controller**: Schedules jobs for each cycle (1st and 20th of month)
- **Scraper**: Queries Wikimedia for available dumps, archives to archive.today
- **Downloader**: Downloads dumps with checksums and retry logic
- **Uploader**: Uploads to Internet Archive with metadata
- **Creator**: Builds torrents with metadata files and webseeds
- **Publisher**: Uploads manifest and .torrent files to R2/Gist/pastebin
- **Seeder**: qBittorrent/Transmission for torrent seeding
- **Monitor**: Web UI and REST API for status monitoring

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed design.

---

## Getting Started

### Prerequisites

- **Server**: Linux (Ubuntu/Debian recommended) with 2TB+ storage
- **Docker**: Docker Engine 24.0+ and Docker Compose v2
- **Bandwidth**: 100 Mbps+ recommended
- **Credentials**: Internet Archive, Cloudflare R2, GitHub, pastebin.com accounts

### Quick Install

```bash
# Clone repository
git clone https://github.com/yourusername/wikiseed-server.git
cd wikiseed-server

# Create directories
mkdir -p data/{db,dumps,torrents,seeder/{config,watch}}

# Copy and edit configuration
cp config.example.yaml config.yaml
cp .env.example .env
# Edit config.yaml and .env with your settings

# Initialize database
docker compose run --rm controller python /app/scripts/init_db.py

# Start services
docker compose up -d

# Check status
docker compose ps
docker compose logs -f
```

### Access Monitor UI

```
http://localhost:8000
```

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for complete production deployment guide.

---

## Development

### Quick Development Setup

```bash
# Clone and setup
git clone https://github.com/yourusername/wikiseed-server.git
cd wikiseed-server

# Create virtual environment
python3.12 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install

# Start development environment
make dev-up

# Run tests
make test

# Check code quality
make lint
```

See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for detailed development guide.

---

## Documentation

### Core Documentation

- **[docs/bigpicture.md](docs/bigpicture.md)** - Mission, strategy, and high-level overview
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** - Container architecture, job queue design, data flow
- **[docs/DATABASE.md](docs/DATABASE.md)** - Complete database schema, indexes, migrations
- **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)** - Production deployment, backups, monitoring, operations
- **[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)** - Development setup, testing, code quality, contribution guide
- **[docs/API.md](docs/API.md)** - Monitor web UI and REST API reference

### Additional Resources

- **[CHANGELOG.md](CHANGELOG.md)** - Version history and release notes
- **[LICENSE](LICENSE)** - AGPL-3.0 license

---

## Technology Stack

### Core Technologies

- **Python 3.12+**: Modern Python with type hints and performance improvements
- **SQLite**: Lightweight database for job queue and state management
- **Docker Compose**: Container orchestration for single-host deployment
- **Flask**: Web framework for Monitor UI and REST API
- **qBittorrent/Transmission**: Off-the-shelf torrent client for seeding

### Key Dependencies

- **requests**: HTTP client for API calls
- **internetarchive**: Internet Archive Python library
- **torf**: Torrent file creation
- **schedule**: Job scheduling
- **pytest**: Testing framework
- **black, ruff, mypy**: Code quality tools

See [requirements.txt](requirements.txt) and [requirements-dev.txt](requirements-dev.txt) for complete lists.

---

## Project Status

**Current Phase**: Documentation and architecture design

- ✅ Complete documentation (bigpicture, architecture, database, deployment, development, API)
- ⏳ Implementation (in progress)
- ⏳ Testing (pending)
- ⏳ Production deployment (pending)

### Roadmap

**Phase 1: Core Pipeline** (Current)
- [ ] Container setup and Docker Compose configuration
- [ ] Database initialization and migrations
- [ ] Job queue implementation
- [ ] Scraper: Wikimedia dump discovery
- [ ] Downloader: Resumable downloads with retry
- [ ] Uploader: Internet Archive integration

**Phase 2: Torrent Creation**
- [ ] Creator: Torrent builder with metadata
- [ ] Publisher: R2/Gist/pastebin upload
- [ ] Seeder: qBittorrent integration
- [ ] Monitor: Basic web UI

**Phase 3: Polish & Launch**
- [ ] Small wiki mode end-to-end testing
- [ ] Monitor: Full dashboard and API
- [ ] Documentation review and cleanup
- [ ] Production deployment
- [ ] First public release

**Phase 4: Enhancements**
- [ ] Academic Torrents auto-submission
- [ ] RSS feed generation
- [ ] Client tools (Python CLI)
- [ ] Performance optimizations

See [docs/bigpicture.md](docs/bigpicture.md) for long-term vision.

---

## Contributing

WikiSeed is an open-source project and welcomes contributions!

### How to Contribute

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/your-feature`
3. **Make your changes** with tests and documentation
4. **Run quality checks**: `make lint && make test`
5. **Commit with conventional commits**: `feat(scraper): add retry logic`
6. **Push and create a pull request**

### Contribution Areas

- **Code**: Implement containers, fix bugs, add features
- **Documentation**: Improve docs, add examples, fix typos
- **Testing**: Add tests, improve coverage, test edge cases
- **Design**: UI/UX improvements for Monitor web interface
- **Operations**: Deployment guides, monitoring, optimization

See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for detailed contribution guidelines.

---

## Use Cases

### For Archivists

- Download complete Wikimedia dumps via torrent
- Verify dumps with checksums (MD5, SHA1, SHA256)
- Access dumps via Internet Archive if torrent unavailable
- Filter dumps by project, language, or date in manifest

### For Researchers

- Programmatic access via REST API
- Manifest API for automated downloads
- Stable URLs and magnet links
- Historical dump availability

### For Mirror Operators

- Seed torrents to distribute bandwidth load
- Pull manifest to mirror latest dumps
- Webseed support for hybrid torrent/HTTP distribution

### For Small Language Communities

- Ensure dumps for small wikis are preserved
- Access dumps even if Wikimedia mirror unavailable
- Long-term availability via Internet Archive

---

## Configuration

### config.yaml

Main configuration file for WikiSeed system.

**Key settings**:
```yaml
wikiseed:
  scheduling:
    cycle_dates: [1, 20]        # Process dumps from 1st and 20th
    publish_deadlines:
      first_cycle: 19           # Publish by 19th
      second_cycle: -1          # Publish by last day of month

  storage:
    max_storage_gb: 2000        # Maximum storage for dumps
    cleanup_threshold_pct: 85   # Start cleanup at 85% full

  download:
    bandwidth_limit_mbps: 0     # 0 = unlimited

  torrents:
    trackers:                   # Public tracker list
      - udp://tracker.opentrackr.org:1337/announce
      - udp://open.stealth.si:80/announce
```

See [config.example.yaml](config.example.yaml) for complete example.

### .env (Secrets)

Environment variables for API credentials.

**Required secrets**:
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
```

See [.env.example](.env.example) for complete template.

---

## Monitoring

### Web UI

Access the Monitor web interface at `http://localhost:8000`

**Features**:
- **Dashboard**: System status, current cycle progress, recent failures
- **Jobs**: Filterable list of all jobs with status
- **Dumps**: List of dumps with download/upload status
- **Torrents**: Published torrents with magnet links and seeding stats

### REST API

Programmatic access to system data at `http://localhost:8000/api/v1`

**Endpoints**:
- `GET /api/v1/status` - System status and metrics
- `GET /api/v1/jobs` - List jobs with filters
- `GET /api/v1/dumps` - List dumps
- `GET /api/v1/torrents` - List torrents
- `GET /api/v1/stats/seeding` - Seeding statistics

Interactive API documentation: `http://localhost:8000/api/docs`

See [docs/API.md](docs/API.md) for complete API reference.

### Command Line

```bash
# Check container status
docker compose ps

# View logs
docker compose logs -f controller

# Check job queue
docker compose exec controller sqlite3 /data/db/jobs.db \
  "SELECT job_type, status, COUNT(*) FROM jobs GROUP BY job_type, status;"

# Check disk usage
df -h /path/to/wikiseed/data
```

---

## Backups

WikiSeed includes automated backup scripts for database and configuration.

### Database Backup

Automated daily backups with cloud upload:

```bash
# Backup script runs daily via cron at 2 AM
/usr/local/bin/wikiseed-backup-db.sh

# Retention: 7 daily, 4 weekly, 12 monthly backups
```

### Manual Backup

```bash
# Backup database
sqlite3 /path/to/data/db/jobs.db ".backup /backups/jobs-$(date +%Y-%m-%d).db"

# Backup configuration
tar -czf wikiseed-config-$(date +%Y-%m-%d).tar.gz config.yaml .env
```

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for complete backup and restore procedures.

---

## Troubleshooting

### Common Issues

**Containers won't start**:
```bash
# Check logs
docker compose logs

# Check disk space
df -h

# Rebuild containers
docker compose down
docker compose build --no-cache
docker compose up -d
```

**Jobs not processing**:
```bash
# Check job queue
docker compose exec controller sqlite3 /data/db/jobs.db \
  "SELECT * FROM jobs WHERE status = 'failed';"

# Restart worker containers
docker compose restart scraper downloader uploader
```

**Disk full**:
```bash
# Clean up Docker images
docker image prune -a -f

# Adjust cleanup threshold in config.yaml
# Lower cleanup_threshold_pct from 85% to 75%
```

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for detailed troubleshooting.

---

## Security

### Best Practices

- **Secrets**: Store credentials in `.env` with `chmod 600` permissions
- **Network**: Bind Monitor UI to localhost or use SSH tunneling for remote access
- **Firewall**: Only expose BitTorrent port (6881), not web UIs
- **Updates**: Enable automatic security updates for OS packages
- **Backups**: Encrypted backups uploaded to cloud storage

### Reporting Security Issues

**DO NOT** open public GitHub issues for security vulnerabilities.

Instead, email: **security@wikiseed.app** (private)

We'll respond within 48 hours and work with you on a fix.

---

## License

### Server Code (This Repository)

**AGPL-3.0** - Strong copyleft requiring source sharing for network use.

See [LICENSE](LICENSE) for full text.

### Client Code (Separate Repository)

**GPL-3.0** - Copyleft encouraging open contributions.

### Documentation

**CC BY-SA 4.0** - Aligns with Wikimedia content licensing.

### Wikimedia Content

Original licenses preserved (GFDL, CC BY-SA 4.0, etc.). WikiSeed redistributes with proper attribution.

---

## Community

### Get Help

- **Documentation**: Start with [bigpicture.md](bigpicture.md) and linked docs
- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: Questions and general discussion

### Stay Updated

- **Releases**: Watch this repository for new releases
- **Blog**: [wikiseed.app/blog](https://wikiseed.app/blog)
- **RSS Feed**: [wikiseed.app/feed.xml](https://wikiseed.app/feed.xml)

### Connect

- **Website**: [wikiseed.app](https://wikiseed.app)
- **Email**: [hello@wikiseed.app](mailto:hello@wikiseed.app)
- **Mastodon**: [@wikiseed@fosstodon.org](https://fosstodon.org/@wikiseed)

---

## Acknowledgments

- **Wikimedia Foundation**: For creating and maintaining the world's free knowledge
- **Internet Archive**: For permanent storage and bandwidth
- **Cloudflare**: For R2 storage and CDN
- **Academic Torrents**: For distribution platform
- **Open Source Community**: For the tools that make WikiSeed possible

---

## Related Projects

- **[Kiwix](https://www.kiwix.org/)**: Offline Wikipedia and Wikimedia content
- **[Xowa](http://xowa.org/)**: Desktop Wikipedia reader
- **[WikiTeam](https://github.com/WikiTeam/wikiteam)**: Wiki archival tools
- **Internet Archive's Wikimedia Collections**: [archive.org/details/wikimediadownloads](https://archive.org/details/wikimediadownloads)

---

<p align="center">
  <strong>WikiSeed</strong><br>
  Ensuring "at least one copy of everything"<br>
  <a href="https://wikiseed.app">wikiseed.app</a>
</p>
