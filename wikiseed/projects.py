"""Wikimedia wiki/project name helpers.

Used by the publisher and uploader to derive the project ("wikipedia",
"wiktionary", ...) from a wiki name ("enwiki", "enwiktionary", ...)."""

# Order matters: longer suffixes first so "wiktionary" wins over "wiki".
_XML_PROJECT_SUFFIXES = (
    ("wiktionary",  "wiktionary"),
    ("wikibooks",   "wikibooks"),
    ("wikinews",    "wikinews"),
    ("wikiquote",   "wikiquote"),
    ("wikisource",  "wikisource"),
    ("wikiversity", "wikiversity"),
    ("wikivoyage",  "wikivoyage"),
    ("wiki",        "wikipedia"),
)

# Wikis whose names end with 'wiki' but are not Wikipedia.
_SPECIAL_WIKI_PROJECTS = {
    "commonswiki":   "commons",
    "metawiki":      "meta",
    "wikidatawiki":  "wikidata",
    "specieswiki":   "wikispecies",
    "mediawikiwiki": "mediawiki",
    "incubatorwiki": "incubator",
    "sourceswiki":   "sources",
    "foundationwiki": "foundation",
}


def project_from_wiki(wiki: str) -> str:
    """'enwiki' -> 'wikipedia', 'enwiktionary' -> 'wiktionary'.

    Special-cased multi-project wikis go via the lookup table;
    unrecognized wikis fall back to the name itself."""
    if wiki in _SPECIAL_WIKI_PROJECTS:
        return _SPECIAL_WIKI_PROJECTS[wiki]
    for suffix, project in _XML_PROJECT_SUFFIXES:
        if wiki.endswith(suffix):
            return project
    return wiki
