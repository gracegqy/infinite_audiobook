"""Fetchers per source_class (DESIGN §5). Each returns the raw story text, which
clean-stage validation then gates (probe 4: deleted/empty wiki pages must be
rejected, not ingested).

Phase 3 scope: gutenberg + creepypasta. nosleep stays disabled until Grace
creates the Reddit OAuth app (§9.2); scp_cn + local_import land Phase 5+.
"""
import html
import html.parser
import json
import re
import urllib.error
import urllib.parse
import urllib.request

from . import config, textproc

ENABLED_SOURCE_CLASSES = ("gutenberg", "creepypasta")


class FetchError(Exception):
    pass


def _get(url: str, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": config.USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as e:  # includes HTTPError for non-2xx
        raise FetchError(f"{e} for {url}") from e


def fetch_gutenberg(gutenberg_id: int) -> tuple[str, str]:
    """Returns (raw_body, source_url). Header/footer stripped (probe 4: 10/10)."""
    url = f"https://www.gutenberg.org/cache/epub/{gutenberg_id}/pg{gutenberg_id}.txt"
    raw = _get(url)
    body, stripped = textproc.strip_gutenberg(raw)
    if not stripped:
        raise FetchError(f"Gutenberg START/END markers not found in {url}")
    return body, url


class _HtmlText(html.parser.HTMLParser):
    SKIP = {"script", "style", "table", "aside", "figure", "sup"}

    def __init__(self):
        super().__init__()
        self.skip = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        if tag in ("p", "br", "div", "h2", "h3") and not self.skip:
            self.parts.append("\n\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def fetch_creepypasta(page_title: str) -> tuple[str, str]:
    """MediaWiki action=parse + HTML strip (probe 4). Returns (text, source_url)."""
    q = urllib.parse.quote(page_title)
    api = (f"https://creepypasta.fandom.com/api.php?action=parse&page={q}"
           f"&format=json&prop=text&redirects=1")
    data = json.loads(_get(api))
    if "error" in data:
        raise FetchError(f"creepypasta page '{page_title}': {data['error'].get('code')}")
    parser = _HtmlText()
    parser.feed(data["parse"]["text"]["*"])
    # no html.unescape here: HTMLParser(convert_charrefs=True) already decoded
    # entities; a second pass would corrupt literal "&amp;"-style story text
    text = "".join(parser.parts)
    canonical = data["parse"]["title"]
    url = f"https://creepypasta.fandom.com/wiki/{urllib.parse.quote(canonical.replace(' ', '_'))}"
    return text, url


def fetch_candidate(candidate: dict) -> tuple[str, str]:
    """Dispatch on the curator candidate's source_class → (raw_text, source_url)."""
    sc = candidate["source_class"]
    ref = candidate["source_ref"]
    if sc == "gutenberg":
        m = re.search(r"\d+", str(ref))
        if not m:
            raise FetchError(f"no Gutenberg id in source_ref {ref!r}")
        return fetch_gutenberg(int(m.group()))
    if sc == "creepypasta":
        return fetch_creepypasta(str(ref))
    raise FetchError(f"source_class {sc!r} not enabled in Phase 3")
