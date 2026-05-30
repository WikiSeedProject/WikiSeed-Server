"""Process-wide config loaded from environment variables at import time."""
import os
from dataclasses import dataclass
from pathlib import Path


def _env(name: str, default=None, required: bool = False) -> str:
    v = os.environ.get(name, default)
    if required and not v:
        raise RuntimeError(f"Required environment variable {name} is not set")
    return v


def _env_int(name: str, default: int) -> int:
    return int(os.environ.get(name, default))


@dataclass(frozen=True)
class Config:
    pg_host: str
    pg_port: int
    pg_db: str
    pg_user: str
    pg_password: str

    data_dir: Path
    manifest_dir: Path
    storage_budget_bytes: int

    version: str
    user_agent: str
    torrent_cdn_base: str

    health_min_seeders: int
    health_below_threshold_hours: int

    r2_account_id: str
    r2_access_key_id: str
    r2_secret_access_key: str
    r2_bucket: str

    ia_access_key: str
    ia_secret_key: str

    qbittorrent_host: str
    qbittorrent_port: int
    qbittorrent_user: str
    qbittorrent_password: str

    github_token: str
    github_repo: str
    github_manifest_branch: str


def _load() -> Config:
    return Config(
        pg_host=_env("POSTGRES_HOST", "postgres"),
        pg_port=_env_int("POSTGRES_PORT", 5432),
        pg_db=_env("POSTGRES_DB", "wikiseed"),
        pg_user=_env("POSTGRES_USER", "wikiseed"),
        pg_password=_env("POSTGRES_PASSWORD", required=True),
        data_dir=Path(_env("WIKISEED_DATA_DIR", "/data")),
        manifest_dir=Path(_env("WIKISEED_MANIFEST_DIR", "/etc/wikiseed/manifest")),
        storage_budget_bytes=_env_int("STORAGE_BUDGET_BYTES", 20_000_000_000_000),
        version=_env("WIKISEED_VERSION", "1.0"),
        user_agent=_env("WIKISEED_USER_AGENT", "WikiSeed.app/1.0"),
        torrent_cdn_base=_env("WIKISEED_TORRENT_CDN_BASE", "https://cdn.wikiseed.app/torrents/"),
        health_min_seeders=_env_int("HEALTH_MIN_SEEDERS", 4),
        health_below_threshold_hours=_env_int("HEALTH_BELOW_THRESHOLD_HOURS", 24),
        r2_account_id=_env("R2_ACCOUNT_ID", ""),
        r2_access_key_id=_env("R2_ACCESS_KEY_ID", ""),
        r2_secret_access_key=_env("R2_SECRET_ACCESS_KEY", ""),
        r2_bucket=_env("R2_BUCKET", "wikiseed"),
        ia_access_key=_env("IA_ACCESS_KEY", ""),
        ia_secret_key=_env("IA_SECRET_KEY", ""),
        qbittorrent_host=_env("QBITTORRENT_HOST", "qbittorrent"),
        qbittorrent_port=_env_int("QBITTORRENT_PORT", 8080),
        qbittorrent_user=_env("QBITTORRENT_USER", "admin"),
        qbittorrent_password=_env("QBITTORRENT_PASSWORD", "adminadmin"),
        github_token=_env("GITHUB_TOKEN", ""),
        github_repo=_env("GITHUB_REPO", ""),
        github_manifest_branch=_env("GITHUB_MANIFEST_BRANCH", "manifest"),
    )


CONFIG = _load()
