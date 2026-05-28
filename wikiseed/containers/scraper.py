"""Scraper — discovers XML and ZIM dumps, writes dumps rows, enqueues download jobs.

Job types handled:
    scrape_xml_current  - walk mediawiki_content_current/{wiki}/{period}/
    scrape_xml_history  - walk mediawiki_content_history/{wiki}/{period}/
    scrape_zim          - walk kiwix/zim/{project}/

A period is considered ready as soon as SHA256SUMS appears in the dated
directory (XML) or when a new dated filename is observed (ZIM). dumps
inserts use ON CONFLICT DO NOTHING against the unique wikimedia_url so the
scraper is safe to re-run.
"""
import logging
import re
import time
from typing import Optional

import requests
from bs4 import BeautifulSoup

from wikiseed import jobs
from wikiseed.config import CONFIG
from wikiseed.db import cursor as db_cursor
from wikiseed.logging_setup import setup

logger = logging.getLogger("scraper")

XML_CURRENT_BASE = "https://dumps.wikimedia.org/other/mediawiki_content_current/"
XML_HISTORY_BASE = "https://dumps.wikimedia.org/other/mediawiki_content_history/"
ZIM_BASE = "https://dumps.wikimedia.org/other/kiwix/zim/"

ZIM_PROJECTS = [
    "wikibooks", "wikinews", "wikipedia", "wikiquote",
    "wikisource", "wikiversity", "wikivoyage", "wiktionary",
]

POLL_INTERVAL_SECONDS = 60

# Wikis that don't follow the {lang}{project} naming pattern.
SPECIAL_WIKIS = {
    "commonswiki", "metawiki", "wikidatawiki", "specieswiki",
    "mediawikiwiki", "incubatorwiki", "sourceswiki", "foundationwiki",
}

# Order matters: longer suffixes first so "wiktionary" wins over "wiki".
_WIKI_SUFFIXES = (
    "wiktionary", "wikibooks", "wikinews", "wikiquote",
    "wikisource", "wikiversity", "wikivoyage", "wiki",
)


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": CONFIG.user_agent})
    return s


def _list_dir(s: requests.Session, url: str) -> list:
    r = s.get(url, timeout=60)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    items = []
    for a in soup.find_all("a"):
        href = a.get("href")
        if not href or href in ("../", "/"):
            continue
        items.append({
            "name": href,
            "url": url.rstrip("/") + "/" + href,
            "is_dir": href.endswith("/"),
        })
    return items


def _parse_sha256sums(text: str) -> dict:
    out = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            out[parts[1].lstrip("*")] = parts[0]
    return out


def _language_from_wiki(wiki: str) -> Optional[str]:
    if wiki in SPECIAL_WIKIS:
        return None
    for suffix in _WIKI_SUFFIXES:
        if wiki.endswith(suffix) and len(wiki) > len(suffix):
            return wiki[: -len(suffix)]
    return None


def _dump_exists_for_url(url: str) -> bool:
    with db_cursor(commit=False) as cur:
        cur.execute("SELECT 1 FROM dumps WHERE wikimedia_url=%s LIMIT 1", (url,))
        return cur.fetchone() is not None


def _period_already_scraped(wiki: str, source_type: str, period: str) -> bool:
    with db_cursor(commit=False) as cur:
        cur.execute(
            "SELECT 1 FROM dumps WHERE wiki_or_project=%s AND source_type=%s AND period=%s LIMIT 1",
            (wiki, source_type, period),
        )
        return cur.fetchone() is not None


def _insert_dump(**kwargs) -> Optional[int]:
    cols = list(kwargs.keys())
    with db_cursor() as cur:
        cur.execute(
            f"INSERT INTO dumps ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))}) "
            "ON CONFLICT (wikimedia_url) DO NOTHING RETURNING id",
            tuple(kwargs.values()),
        )
        row = cur.fetchone()
        return row["id"] if row else None


def scrape_xml(source_type: str, base_url: str) -> None:
    assert source_type in ("xml_current", "xml_history")
    s = _session()

    wikis = [i for i in _list_dir(s, base_url) if i["is_dir"]]
    logger.info("xml: found %d wikis under %s", len(wikis), base_url)

    for w in wikis:
        wiki = w["name"].rstrip("/")
        try:
            periods = [i for i in _list_dir(s, w["url"]) if i["is_dir"]]
        except requests.RequestException as e:
            logger.warning("failed listing %s: %s", w["url"], e)
            continue

        for p in periods:
            period = p["name"].rstrip("/")
            if not re.match(r"^\d{4}-\d{2}$", period):
                continue
            if _period_already_scraped(wiki, source_type, period):
                continue

            try:
                files = _list_dir(s, p["url"])
            except requests.RequestException as e:
                logger.warning("failed listing %s: %s", p["url"], e)
                continue

            sums_url = next((f["url"] for f in files if f["name"] == "SHA256SUMS"), None)
            if not sums_url:
                continue

            try:
                sums_text = s.get(sums_url, timeout=60).text
            except requests.RequestException as e:
                logger.warning("failed fetching %s: %s", sums_url, e)
                continue

            sums = _parse_sha256sums(sums_text)
            language = _language_from_wiki(wiki)
            new_count = 0

            for fname, sha in sums.items():
                if fname == "SHA256SUMS":
                    continue
                file_url = p["url"].rstrip("/") + "/" + fname
                if _dump_exists_for_url(file_url):
                    continue
                dump_id = _insert_dump(
                    wiki_or_project=wiki,
                    language=language,
                    source_type=source_type,
                    period=period,
                    wikimedia_url=file_url,
                    sha256_wikimedia=sha,
                )
                if dump_id is not None:
                    jobs.enqueue("download", {"dump_id": dump_id})
                    new_count += 1

            logger.info("scraped %s/%s/%s: %d new files", source_type, wiki, period, new_count)


def scrape_zim() -> None:
    s = _session()

    for project in ZIM_PROJECTS:
        proj_url = ZIM_BASE + project + "/"
        try:
            files = _list_dir(s, proj_url)
        except requests.RequestException as e:
            logger.warning("failed listing %s: %s", proj_url, e)
            continue

        # filename pattern: {project}_{lang}_all_{scope}_{YYYY-MM}.zim
        # we only take 'all' topic, all three scopes, latest period per (lang, scope).
        pattern = re.compile(
            rf"^{re.escape(project)}_([a-z0-9\-_]+)_all_(maxi|nopic|mini)_(\d{{4}}-\d{{2}})\.zim$"
        )

        latest: dict = {}
        for f in files:
            if f["is_dir"]:
                continue
            m = pattern.match(f["name"])
            if not m:
                continue
            lang, scope, period = m.group(1), m.group(2), m.group(3)
            key = (lang, scope)
            if key not in latest or period > latest[key][2]:
                latest[key] = (f["url"], f["name"], period)

        new_count = 0
        for (lang, scope), (url, _fname, period) in latest.items():
            if _dump_exists_for_url(url):
                continue
            dump_id = _insert_dump(
                wiki_or_project=project,
                language=lang,
                source_type="zim",
                period=period,
                wikimedia_url=url,
                zim_scope=scope,
                zim_topic="all",
            )
            if dump_id is not None:
                jobs.enqueue("download", {"dump_id": dump_id})
                new_count += 1

        logger.info("scraped zim %s: %d candidates, %d new", project, len(latest), new_count)


HANDLERS = {
    "scrape_xml_current": lambda payload: scrape_xml("xml_current", XML_CURRENT_BASE),
    "scrape_xml_history": lambda payload: scrape_xml("xml_history", XML_HISTORY_BASE),
    "scrape_zim": lambda payload: scrape_zim(),
}


def main() -> None:
    setup("scraper")
    logger.info("scraper started")
    while True:
        job = jobs.claim(list(HANDLERS.keys()))
        if not job:
            time.sleep(POLL_INTERVAL_SECONDS)
            continue

        try:
            HANDLERS[job["job_type"]](job["payload"])
            jobs.complete(job["id"])
            logger.info("completed %s id=%d", job["job_type"], job["id"])
        except Exception as e:
            logger.exception("job %s id=%d failed", job["job_type"], job["id"])
            jobs.fail(job["id"], str(e))


if __name__ == "__main__":
    main()
