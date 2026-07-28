"""Tag stage (DESIGN §5): one cheap Claude call at ingest (~$0.01, R10).
Controlled vocab per kind + verbatim labels kept; missing values stay NULL
(nullable-over-required, bank schema checklist)."""
import json
import re

from . import config

TAG_PROMPT = """Tag this story for a personal fiction library. Story metadata:
title: {title} · author: {author} · language: {language}

Opening excerpt:
{excerpt}

Return ONLY a JSON object:
{{"era": one of {era_vocab} or null,
  "subgenre": 1-3 of {subgenre_vocab},
  "origin": one of {origin_vocab} or null,
  "themes": 2-5 short free-text theme labels}}
Base era/origin on the author and text; if genuinely unsure, use null."""


def parse_tags(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("no JSON object in tag response")
    return json.loads(m.group())


def normalize_tag(kind: str, value: str) -> str | None:
    """Map a verbatim label onto the controlled vocab; None = uncontrolled kind."""
    vocab = config.CONTROLLED_VOCAB.get(kind)
    if vocab is None:
        return None
    v = value.strip().lower().replace(" ", "-").replace("_", "-")
    return v if v in vocab else None


def free_value_norm(verbatim: str) -> str:
    """Aggregation key for an UNCONTROLLED kind's label. The single copy: tag
    writes go through it and db._migrate_tag_value_norm re-derives old rows with
    it, so a stored key can never disagree with a freshly computed one.

    Phase 6 aggregates on (kind, value_norm), so "Unreliable Narrator" and
    "unreliable-narrator" must collapse to one key — they did not before this
    was hoisted out, and the two spellings sat in the DB as separate themes.
    """
    return re.sub(r"[\s_]+", "-", str(verbatim).strip().lower())


def tag_rows(story_id: str, tags: dict, author: str | None,
             language: str) -> list[tuple]:
    """Flatten the LLM tag object + known fields into tags-table rows
    (story_id, kind, value_verbatim, value_norm). Pure logic — unit-tested."""
    rows = []

    def add(kind, verbatim):
        if not verbatim:
            return
        norm = normalize_tag(kind, str(verbatim))
        if norm is None and kind in config.CONTROLLED_VOCAB:
            return  # off-vocabulary value for a controlled kind: drop, stays NULL
        # uncontrolled kinds use the SAME hyphen-collapse normalization as
        # controlled ones — Phase 6 aggregates ratings on (kind, value_norm),
        # so "Body Horror" and "body-horror" must land on one key
        rows.append((story_id, kind, str(verbatim), norm or free_value_norm(verbatim)))

    add("era", tags.get("era"))
    add("origin", tags.get("origin"))
    for sg in (tags.get("subgenre") or [])[:3]:
        add("subgenre", sg)
    for th in (tags.get("themes") or [])[:5]:
        add("theme", th)
    if author:
        rows.append((story_id, "author", author, author.strip().lower()))
    rows.append((story_id, "language", language, language))
    # dedupe on the PK (kind, value_norm)
    seen, out = set(), []
    for r in rows:
        pk = (r[1], r[3])
        if pk not in seen:
            seen.add(pk)
            out.append(r)
    return out


def run_tagging(conn, story_id: str, title: str, author: str | None,
                language: str, text: str) -> list[tuple]:
    client = config.anthropic_client()
    prompt = TAG_PROMPT.format(
        title=title, author=author or "unknown", language=language,
        excerpt=text[:1500],
        era_vocab=config.CONTROLLED_VOCAB["era"],
        subgenre_vocab=config.CONTROLLED_VOCAB["subgenre"],
        origin_vocab=config.CONTROLLED_VOCAB["origin"])
    resp = client.messages.create(model=config.TAG_MODEL, max_tokens=500,
                                  messages=[{"role": "user", "content": prompt}])
    tags = parse_tags("".join(b.text for b in resp.content if b.type == "text"))
    rows = tag_rows(story_id, tags, author, language)
    conn.executemany(
        "INSERT OR IGNORE INTO tags(story_id, kind, value_verbatim, value_norm) "
        "VALUES(?,?,?,?)", rows)
    conn.commit()
    print(f"[tag] {len(rows)} tags for {story_id}")
    return rows
