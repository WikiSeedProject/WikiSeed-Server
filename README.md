# WikiSeed-Server

Backend for the WikiSeed Wikimedia preservation project. Discovers Wikimedia
dump publications, downloads them, mirrors them to Internet Archive, creates
torrents, seeds them, monitors swarm health, and publishes the manifest that
all downstream WikiSeed clients consume.

The full design is in the project's design document. This README covers what's
in the repo and how to run it.

## Status

Working:

- Project skeleton, Docker images, docker-compose
- PostgreSQL schema and job queue
- Calendar scheduler (`controller`)
- Discovery of XML current/history dumps and Kiwix ZIM files (`scraper`)
- File downloads with Range-resume and hash verification (`downloader`)

Stubbed (runnable, but `raise NotImplementedError` inside):

- `creator` — torrent generation
- `uploader` — Internet Archive upload
- `seeder` — qBittorrent integration
- `health_monitor` — tracker scraping and redownload triggering
- `storage_manager` — HDD budget enforcement
- `publisher` — manifest + status JSON to R2 and GitHub

Each stub's docstring explains exactly what needs to be implemented and which
library to use.

## Repo layout

```
.
├── docker-compose.yml         all 9 services + postgres + qbittorrent
├── Dockerfile                 single image used by every wikiseed service
├── requirements.txt           pinned Python deps
├── .env.example               copy to .env and fill in
├── db/
│   └── schema.sql             loaded once on first postgres start
└── wikiseed/
    ├── config.py              env-driven Config dataclass
    ├── db.py                  psycopg2 cursor helper
    ├── jobs.py                claim / complete / fail on the jobs table
    ├── logging_setup.py
    ├── trackers.py            public tracker list
    ├── containers/            one module per service, each with main()
    │   ├── controller.py
    │   ├── scraper.py
    │   ├── downloader.py
    │   ├── creator.py
    │   ├── uploader.py
    │   ├── seeder.py
    │   ├── health_monitor.py
    │   ├── storage_manager.py
    │   └── publisher.py
    └── templates/             boilerplate README/LICENSE/VERSION for torrents
```

## Running

```
cp .env.example .env          # fill in secrets
docker compose up -d --build  # postgres, qbittorrent, all wikiseed services
docker compose logs -f controller scraper downloader
```

The schema is loaded by postgres on first start. To reload, remove the
`postgres_data` volume.

To kick the pipeline manually (without waiting for the controller's schedule):

```
docker compose exec postgres psql -U wikiseed -c \
  "INSERT INTO jobs (job_type) VALUES ('scrape_zim');"
```

## Architecture

A single Python image (`Dockerfile`) is run with 9 different `command:` entries
in `docker-compose.yml` — one per logical service. They all share the
`wikiseed` package on `PYTHONPATH`.

Coordination is exclusively through PostgreSQL:

- `jobs` table — `FOR UPDATE SKIP LOCKED` queue, safe across replicas
- `dumps`, `torrents`, `torrent_dumps` — domain state
- `health_events` — append-only audit
- `scheduler_state` — controller's last-run timestamps (idempotent restarts)

There is no message broker, no Redis, no Celery — just polling Postgres.

## Notes for ongoing implementation

- The downloader writes files to `/data/{xml_current|xml_history|zim}/...`
  inside the container, mapped to `${WIKISEED_DATA_DIR}` on the host. The
  creator and seeder containers mount the same volume.
- Job retries: `jobs.fail(job_id, error)` defaults to retry up to 3 times,
  resetting to pending. Pass `retry=False` for hard failures.
- The downloader enqueues `upload_to_ia` on success; the uploader (when
  implemented) should enqueue `create_torrent` once every dump in a group is
  IA-confirmed; the creator should enqueue `register_torrent` and
  `publish_manifest`.

## License

AGPL-3.0
