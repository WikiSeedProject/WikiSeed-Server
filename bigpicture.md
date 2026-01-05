# WikiSeed: Big Picture

## Mission

WikiSeed ensures "at least one copy of everything" from all Wikimedia projects and languages. The project archives Wikimedia database dumps and distributes them via torrents and Internet Archive, with a focus on smaller language communities often overlooked by other backup projects.

## Architecture Overview

WikiSeed uses a split architecture:

- **Server** (home infrastructure): Handles dump discovery, downloading, processing, torrent creation, and seeding
- **Cloudflare** (cloud): Hosts the website, API, manifest files, and .torrent files via R2 storage
- **Clients** (distributed): Allow anyone to download and seed archived dumps based on their preferences and capacity

This split keeps bandwidth-intensive seeding on the home server while offloading web traffic to Cloudflare.

## Server Components

### Processor

The processor is split into granular scripts for easier debugging, testing, and recovery from failures. Each script can be rerun independently without restarting the entire pipeline.

### Processor Scripts

| Script | Purpose | Input | Output |
|--------|---------|-------|--------|
| `discover.py` | Query Wikimedia for available dumps | Cycle date, config | List of dumps to fetch |
| `download.py` | Download dumps from Wikimedia | Dump list | Downloaded files |
| `upload_ia.py` | Upload dumps to Internet Archive | Downloaded files | IA item identifiers |
| `archive.py` | Archive dump pages to archive.today | Dump URLs | Archive URLs |
| `decompress.py` | Create uncompressed versions | Compressed files | Uncompressed files |
| `torrent.py` | Create torrents with webseeds | Files, IA URLs | .torrent files |
| `manifest.py` | Generate manifest, status, hashes | All metadata | JSON/TXT files |
| `publish.py` | Push to R2, Gist, pastebin | Manifest, torrents | Confirmation |

### Processor Orchestration

A thin orchestrator script or sequential cron jobs call each script in order. State is passed between scripts via files or a small SQLite database tracking progress per cycle.

### Processor Failure Recovery

If a script fails, fix the issue and rerun from that point. Earlier steps don't need to repeat. The orchestrator tracks which steps completed successfully for each cycle.

### Seeder
Off-the-shelf torrent client (qBittorrent or Transmission) running in a container, watching a directory for new torrents. No custom code required.

## Cloudflare Components

### R2 Storage
Stores:
- Manifest files (JSON and TXT)
- Status files (JSON and TXT)
- .torrent files

### Web/API
- Website at wikiseed.app
- API endpoints for manifest access
- RSS/Atom feeds for torrent discovery
- Web tool for browsing and filtering torrents

## Dump Types

### Regular Dumps (1st and 20th cycles)
- pages-articles (current article content)
- pages-meta-current (current revisions with metadata)
- abstract (article summaries)
- all-titles (list of page titles)
- stub-articles / stub-meta-history (skeleton structure)
- SQL tables (categorylinks, pagelinks, imagelinks, redirect, site_stats, etc.)

### History Dumps (1st cycle only)
- pages-meta-history (full revision history)
- abstract
- all-titles
- stubs
- SQL tables

History torrents are self-contained and do not require the regular torrent.

### Not Included (for now)
- Wikimedia Commons media files (out of scope due to size)

## Torrent Structure

### Naming Convention
```
wikimedia-dumps-YYYY-MM-DD.torrent                (compressed)
wikimedia-dumps-YYYY-MM-DD-uncompressed.torrent
wikimedia-dumps-YYYY-MM-DD-full-history.torrent   (1st cycle only, compressed)
```

### 1st Cycle Torrents
- Compressed regular dump
- Uncompressed regular dump
- Compressed history dump (self-contained)

### 20th Cycle Torrents
- Compressed regular dump
- Uncompressed regular dump

### Torrent Contents
Each torrent is one large bundle for the dump date. Users select which files they want within the torrent (by project, language, etc.). Files use original Wikimedia filenames for provenance.

Example folder structure:

torrent-root/
├── compressed/
│   └── en/
│       └── wikipedia/
│           └── ...
├── uncompressed/
│   └── en/
│       └── wikipedia/
│           └── ...
├── tools/
│   ├── wikiseed/          # Simple Python scripts for common tasks (GPL)
│   ├── third-party/       # Bundled external tools (their original licenses)
│   └── LICENSES.txt       # License documentation for all tools
├── README.txt             # Format explanations, links to external tools
├── LICENSE.txt            # WikiSeed and content licenses
├── VERSION.txt            # Version of docs/tools included
├── HASH.json              # Checksums: MD5, SHA1 (Wikimedia), SHA256 (generated)
├── HASH.txt
├── STATUS.json            # Pass/fail status of every included dump
├── STATUS.txt
├── ARCHIVE_URLS.json      # archive.today links for dump pages
└── ARCHIVE_URLS.txt

## Timing and Cycles

### Dump Cadence
Wikimedia initializes dumps on the 1st and 20th of each month.

### Embargo
One dump behind: process the previous cycle while the current one is being generated.

### Publish Deadlines
- 1st cycle dumps: Publish on the 19th (or sooner if everything is done with no errors)
- 20th cycle dumps: Publish on the last day of the month (or sooner if everything is done with no errors)

### Failure Handling
- Retry with exponential backoff on failures
- If a wiki's dump fails after retries, continue with successful wikis
- Accept gaps and fill in next cycle if possible
- Document failures in README and in manifest

### Date Window
For a given cycle, include dumps dated within that window only (e.g., June 1st cycle includes dumps dated June 1-19).

## Manifest

### Format
Published in both JSON and TXT for maximum accessibility.

### Contents
- List of torrents with magnet links and .torrent URLs
- Per-torrent metadata: dump date, compressed/uncompressed/history, total size
- Per-file metadata: project, language, file size, filename
- Checksums (MD5, SHA1, SHA256)
- Wikimedia source URLs
- Internet Archive item identifiers
- Webseed URLs
- Last-updated timestamp
- Version field for backwards compatibility

### Distribution
- Cloudflare R2 (primary)
- Internet Archive
- GitHub Gist
- pastebin.com

## Status File

### Format
JSON and TXT, published alongside manifest.

### Contents
- Per-wiki status for each release:
  - Success
  - Failed on Wikimedia side (dump never appeared or marked failed)
  - Failed on WikiSeed side (download error, IA upload failed, etc.)
  - Not available in date window
- Deprecated flag for problematic releases

## Archival and Redundancy

### Internet Archive
- All dumps uploaded as IA items
- Used as webseed for torrents
- Permanent storage and bandwidth offload

### archive.today
- Dump index pages archived via API
- Dumpstatus pages archived
- Provides snapshots of Wikimedia's dump state

### Text File Redundancy
Manifest, status, and hash files uploaded to:
- Internet Archive (as part of dump items)
- GitHub Gist
- pastebin.com

### Webseeds
Each torrent includes webseeds pointing to:
- Internet Archive URLs
- Listed Wikimedia Dump Mirrors
- Wikimedia server (initial download)

## Clients

### Python CLI
- Reads manifest, filters based on configuration
- Configuration options: languages, projects, date ranges, storage limits
- Storage management options:
  - Pause and warn (default)
  - Drop uncompressed before compressed
  - Drop oldest first
  - Minimum retention period
- Backends for different torrent clients:
  - qBittorrent API
  - Transmission API
  - Deluge API
  - Output magnets/files only (manual mode)
- Can optionally pull tracker stats to inform decisions
- Licensed under GPL

### Web Tool
- Vanilla HTML/CSS/JS (no framework, no build step)
- Browse and filter available torrents
- Copy magnet links
- Download .torrent files
- Generate batch of magnets or zip of .torrent files
- Links to Internet Archive for non-torrent users

### Other Access Methods
- RSS/Atom feeds (works with torrent clients' built-in RSS)
- Static URLs (e.g., latest-compressed.torrent)
- Direct API access
- Academic Torrents listings

## Distribution Channels

### Primary
- WikiSeed website and API
- Torrent swarm with public trackers (found at https://torrends.to/torrent-tracker-list/)

### Secondary
- Academic Torrents (auto-upload via API)
- Internet Archive (direct downloads for non-torrent users)
- iTorrents.org

### Future
- Wikimedia community pages (via bot, outside project scope)

## Announcements

### Channels
- Blog on wikiseed.app
- Mailing list
- RSS feed

All three connected so announcements propagate to all channels.

## Statistics

### Tracked Metrics
- Seeders/ratio per torrent (from tracker scrapes)
- Download counts
- Website traffic
- Processing stats (time, sizes, success rates per cycle)
- Total file upload/download bandwidth

## Monitoring

- Email alerts on pipeline failures
- Dry run mode for validation without downloads/uploads
- Small wiki mode for testing full flow quickly

## Retention

- Keep torrents as long as storage allows
- Prune oldest first when storage fills
- Seed all torrents until pruned
- Assumption: by pruning time, sufficient external seeders exist plus IA webseed remains available

## Security

- Credentials (IA, Gist, pastebin, archive.today, Academic Torrents, SMTP) stored following best practices
- FIDO MFA on Cloudflare account
- Specific credential storage approach TBD in technical planning

## Feedback

- GitHub Issues for bug reports and feature requests
- Email for general inquiries

## Licensing

### Server Code
AGPL - Strong copyleft, requires source sharing for network use.

### Client Code
GPL - Copyleft, encourages open contributions.

### WikiSeed Tools
GPL - Same as client code for simplicity.

### Third-Party Tools
Original licenses preserved. Each tool's license documented in LICENSES.txt.

### Documentation
CC BY-SA - Aligns with Wikimedia content licensing.

### Wikimedia Content
Original licenses (GFDL, CC BY-SA 4.0, etc.) preserved. WikiSeed redistributes with proper attribution.

## Succession

- Server and client code open source on GitHub
- Comprehensive documentation for future maintainers
- Architecture designed for handoff if original maintainer stops

## Testing

### Dry Run Mode
Pipeline runs through all logic but skips actual downloads and uploads. Validates configuration, API connections, and manifest generation.

### Small Wiki Mode
Processes only a handful of tiny wikis (a few MB each). Tests full end-to-end flow in minutes instead of days.

## Technical Stack

### Server
- Python (standard library + minimal dependencies)
- SQLite or filesystem markers for state
- Cron for scheduling
- Docker for seeder container

### Cloudflare
- R2 for storage
- Pages or Workers for web/API
- Domain: wikiseed.app

### Clients
- Python CLI (requests, qbittorrent-api)
- Vanilla JavaScript web tool

## Future Considerations

- Bandwidth/rate limiting for Wikimedia downloads (good citizenship)
- Wikimedia Commons media dumps (separate project)
- Second server when first reaches capacity
