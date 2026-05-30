"""Filesystem layout under CONFIG.data_dir.

Two stages:

1. Pre-torrent ("canonical"). The downloader writes here. The uploader
   reads from here. Layout:
       {data_dir}/xml_current/{wiki}/{period}/{filename}
       {data_dir}/xml_history/{wiki}/{period}/{filename}
       {data_dir}/zim/{project}/{filename}

2. Staged-for-torrent. The creator moves files here once a torrent is
   minted; this is also what qBittorrent seeds from. Layout:
       {data_dir}/torrents/{torrent_name}/{filename}
       {data_dir}/torrents/{torrent_name}/README.txt
       ... (LICENSE.txt, VERSION.txt, SOURCES.json)
       {data_dir}/torrents/.torrents/{torrent_name}.torrent

The storage manager drops a torrent by deleting its staged directory;
canonical paths have already been consumed by the creator at that point.
"""
from pathlib import Path

from wikiseed.config import CONFIG


def canonical_download_path(dump: dict) -> Path:
    """Where the downloader writes a freshly-downloaded dump."""
    filename = Path(dump["wikimedia_url"]).name
    if dump["source_type"] == "xml_current":
        return CONFIG.data_dir / "xml_current" / dump["wiki_or_project"] / dump["period"] / filename
    if dump["source_type"] == "xml_history":
        return CONFIG.data_dir / "xml_history" / dump["wiki_or_project"] / dump["period"] / filename
    return CONFIG.data_dir / "zim" / dump["wiki_or_project"] / filename


def torrent_staging_dir(torrent_name: str) -> Path:
    return CONFIG.data_dir / "torrents" / torrent_name


def torrent_file_path(torrent_name: str) -> Path:
    return CONFIG.data_dir / "torrents" / ".torrents" / f"{torrent_name}.torrent"


def qbittorrent_save_path() -> Path:
    """save_path qBittorrent uses when loading WikiSeed torrents. The torrent
    files reference filenames relative to this directory."""
    return CONFIG.data_dir / "torrents"
