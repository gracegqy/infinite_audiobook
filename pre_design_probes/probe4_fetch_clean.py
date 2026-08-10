#!/usr/bin/env python3
"""Probe 4: fetch + clean real samples from the three source classes.

Throwaway code — no authority after Phase 1. Stdlib only.
Outputs cleaned text to data/interim/probe4/ and a summary to stdout.
Questions to answer (TASKS.md §1.4):
  - Does each source fetch reliably (status codes, formats)?
  - Does boilerplate stripping work (Gutenberg header/footer, wiki chrome)?
  - Paragraph segmentation sane? (counts, median para length)
  - What dedup key works? (proposal: sha1 of normalized title + first 500 normalized chars)
"""
import hashlib
import html
import html.parser
import json
import pathlib
import re
import sys
import urllib.request

OUT = pathlib.Path(__file__).resolve().parents[1] / "data" / "interim" / "probe4"
UA = {"User-Agent": "infinite-audiobook-probe/0.1 (personal research; contact graceguqianying@uchicago.edu)"}

def get(url, timeout=30):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read().decode("utf-8", errors="replace")

def norm(s):
    return re.sub(r"\s+", " ", s).strip().lower()

def dedup_key(title, text):
    return hashlib.sha1((norm(title) + "|" + norm(text)[:500]).encode()).hexdigest()[:16]

def paragraphs(text):
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    return paras

def report(source, title, text, notes=""):
    paras = paragraphs(text)
    lens = sorted(len(p) for p in paras) or [0]
    med = lens[len(lens) // 2]
    key = dedup_key(title, text)
    safe = re.sub(r"[^a-z0-9]+", "_", norm(title))[:60]
    d = OUT / source
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{safe}.txt").write_text(text)
    print(f"  OK  {source:12s} {title[:46]:46s} chars={len(text):>7d} paras={len(paras):>4d} "
          f"med_para={med:>4d} key={key} {notes}")
    return {"source": source, "title": title, "chars": len(text), "paras": len(paras), "key": key}

# ---------------- Gutenberg ----------------
GUTENBERG = [
    (84, "Frankenstein"), (345, "Dracula"), (43, "Jekyll and Hyde"),
    (174, "The Picture of Dorian Gray"), (932, "The Fall of the House of Usher"),
    (10007, "Carmilla"), (209, "The Turn of the Screw"), (8492, "The King in Yellow"),
    (389, "The Great God Pan"), (11438, "The Willows"),
]

def clean_gutenberg(raw):
    m = re.search(r"\*\*\* ?START OF (?:THE|THIS) PROJECT GUTENBERG EBOOK.*?\*\*\*", raw)
    n = re.search(r"\*\*\* ?END OF (?:THE|THIS) PROJECT GUTENBERG EBOOK.*?\*\*\*", raw)
    body = raw[m.end():n.start()] if m and n else raw
    return body.strip(), bool(m and n)

def probe_gutenberg():
    print("\n[Gutenberg]")
    results = []
    for gid, title in GUTENBERG:
        url = f"https://www.gutenberg.org/cache/epub/{gid}/pg{gid}.txt"
        try:
            status, raw = get(url)
            body, stripped = clean_gutenberg(raw)
            results.append(report("gutenberg", title, body,
                                  notes=("hdr/ftr stripped" if stripped else "MARKERS NOT FOUND")))
        except Exception as e:
            print(f"  FAIL gutenberg {title}: {e}")
    return results

# ---------------- Reddit r/NoSleep ----------------
def probe_nosleep():
    print("\n[Reddit r/NoSleep top.json]")
    results = []
    try:
        status, raw = get("https://www.reddit.com/r/nosleep/top.json?t=year&limit=10&raw_json=1")
        posts = json.loads(raw)["data"]["children"]
    except Exception as e:
        print(f"  FAIL listing: {e}")
        return results
    for p in posts:
        d = p["data"]
        text = d.get("selftext", "")
        # strip common nosleep footers/promo lines (heuristic: trailing lines with links)
        text = re.sub(r"\n+(\[.*?\]\(.*?\)|\s*[-*_]{3,}\s*)(\n|$)+\Z", "\n", text)
        results.append(report("nosleep", d["title"], text,
                              notes=f"ups={d.get('ups')}"))
    return results

# ---------------- Creepypasta wiki (Fandom MediaWiki API) ----------------
CREEPY = ["Candle Cove", "The Russian Sleep Experiment", "Psychosis", "NoEnd House",
          "Smile Dog", "Ben Drowned", "The Rake", "Ted the Caver", "Jeff the Killer",
          "Squidward's Suicide"]

class Text(html.parser.HTMLParser):
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

def probe_creepypasta():
    print("\n[Creepypasta wiki]")
    results = []
    for title in CREEPY:
        q = urllib.parse.quote(title)
        url = f"https://creepypasta.fandom.com/api.php?action=parse&page={q}&format=json&prop=text&redirects=1"
        try:
            status, raw = get(url)
            data = json.loads(raw)
            if "error" in data:
                print(f"  MISS creepypasta {title}: {data['error'].get('code')}")
                continue
            h = data["parse"]["text"]["*"]
            tp = Text()
            tp.feed(h)
            text = html.unescape("".join(tp.parts))
            # drop wiki chrome: nav/category cruft collapses to short junk paras; keep paras >= 40 chars
            paras = [p for p in paragraphs(text) if len(p) >= 40]
            text = "\n\n".join(paras)
            results.append(report("creepypasta", data["parse"]["title"], text))
        except Exception as e:
            print(f"  FAIL creepypasta {title}: {e}")
    return results

if __name__ == "__main__":
    import urllib.parse
    OUT.mkdir(parents=True, exist_ok=True)
    all_r = probe_gutenberg() + probe_nosleep() + probe_creepypasta()
    keys = [r["key"] for r in all_r]
    print(f"\nTotal cleaned: {len(all_r)}; dedup keys unique: {len(set(keys))}/{len(keys)}")
