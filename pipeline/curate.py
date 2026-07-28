"""Curation stage (DESIGN §5): Messages API + web_search against the standing
reputation bar + active channel criteria. Model is fixed config — never
auto-escalated (R14)."""
import json
import re

from . import config, db, verify

PROMPT_TEMPLATE = """You are the curator for a private read-aloud fiction library \
(single listener, personal use).

Find {batch} highly-reputed SHORT stories (standalone works under ~15,000 words —
not novels, not multi-story collections) matching ALL channel criteria:
- Genre: {genre}
- Language: {language}
- Topics/themes: {topics}
- Era: {era}
- Avoid: {avoid}
- Extra criteria: {extra}

REPUTATION BAR (channel-independent): every candidate must carry checkable evidence —
a NAMED list, essay, award, ranking, or ratings page that vouches for it (e.g. "NPR's
100 Best Horror list", "Gutenberg top-100 downloads"). No vague "widely considered".
Use web search to verify evidence rather than relying on memory. If you could not
verify a claim, flag it honestly in "unverified".

BALANCE — this channel wants BOTH halves, and a batch that is all one kind is a
failed batch. Aim for roughly half public-domain classics and half modern web
fiction (adjust if the criteria above clearly favor one). Report what you could
not fill rather than silently substituting more of the easy kind.

SOURCING — the pipeline fetches your `source_ref` literally and rejects it
mechanically, so an unchecked reference wastes the whole candidate:

- **Gutenberg:** `source_ref` is the ebook id of a STANDALONE edition containing
  ONLY that story. Collection volumes ("The Works of...", "Complete Tales...",
  "The King in Yellow") are rejected on length.
  Standalone editions of famous short stories DO exist on Gutenberg and are worth
  searching for — this library already holds several found that way (ebook 1952 =
  The Yellow Wallpaper, 375 = An Occurrence at Owl Creek Bridge, 11438 = The
  Willows). Search Gutenberg for the individual title, check the ebook's own page,
  and confirm from its length and table of contents that it is the single story.
  Spend the search effort: finding the standalone id is the job, not an optional
  extra. Only if a genuine search turns up nothing but collections should you drop
  the candidate — and never substitute the collection id.
- **Creepypasta:** `source_ref` is a wiki page that actually CONTAINS the story
  text. Many pages are stubs: deleted-for-quality notices, copyright-removal
  notices pointing at the author's own site, or link-only navigation pages. Open
  the page and confirm the prose is there. If it is a stub, DROP the candidate.
- **Never guess.** `source_ref` must never be "unknown", empty, a title, or a
  URL you did not open. A candidate without a verified reference is worthless —
  drop it and propose a different story instead.

Verified candidates beat unusable ones, so dropping a genuinely unavailable story
is correct. But dropping is the last resort, not the cheap way out of a search:
an all-modern batch because classics "were all in collections" is the specific
failure to avoid.

Do NOT propose any of these already-known titles:
{exclusions}

Return ONLY a JSON array (no prose around it), each element:
{{"title": str, "author": str, "year": int or null,
  "source_class": "gutenberg"|"creepypasta",
  "source_ref": "<Gutenberg ebook id number>"|"<creepypasta wiki page title>",
  "license_class": "pd"|"modern_private",
  "evidence": [str, ...], "unverified": [str, ...]}}"""

CURATION_BATCH_SIZE_DEFAULT = config.CURATION_BATCH_SIZE

SOURCE_HINTS = {
    "en": "Project Gutenberg plain text (public domain) or creepypasta-wiki pages",
    "fr": "Project Gutenberg plain text (French-language public domain)",
    "zh": "Project Gutenberg plain text (Chinese-language public domain)",
}


def channel_list_field(channel, key: str) -> list[str]:
    """topics_json / exclusions_json → list. Stored as JSON so the editor can
    round-trip them; tolerant of nulls and of a plain string typed by hand."""
    raw = channel[key] if key in channel.keys() else None
    if not raw:
        return []
    try:
        val = json.loads(raw)
    except (TypeError, ValueError):
        return [s.strip() for s in str(raw).split(",") if s.strip()]
    if isinstance(val, list):
        return [str(v).strip() for v in val if str(v).strip()]
    return [str(val).strip()] if str(val).strip() else []


def build_prompt(channel, known_titles: list[str],
                 batch: int = config.CURATION_BATCH_SIZE,
                 taste_profile: str | None = None) -> str:
    # every editable channel field reaches the prompt — an editor whose fields
    # changed nothing would be a lie (R12, TASKS Phase 5 gate)
    prompt = PROMPT_TEMPLATE.format(
        batch=batch,
        genre=channel["genre"] or "any",
        language=channel["language"],
        topics=", ".join(channel_list_field(channel, "topics_json")) or "any",
        era=channel["era"] or "any",
        avoid=", ".join(channel_list_field(channel, "exclusions_json")) or "nothing",
        extra=channel["extra_criteria"] or "none",
        source_hint=SOURCE_HINTS.get(channel["language"], SOURCE_HINTS["en"]),
        exclusions="\n".join(f"- {t}" for t in known_titles) or "(none yet)",
    )
    if taste_profile:  # Phase 6
        prompt += f"\n\nLISTENER TASTE PROFILE (weight your picks):\n{taste_profile}"
    return prompt


def parse_candidates(text: str, batch: int = CURATION_BATCH_SIZE_DEFAULT) -> list[dict]:
    """Extract the JSON array from the response (tolerates a ```json fence).
    The unfenced fallback anchors on "[{" ... "}]" so brackets in surrounding
    prose ("[NPR list]") can't poison the match."""
    m = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.S) or \
        re.search(r"(\[\s*\{.*\}\s*\])", text, re.S)
    if not m:
        # Name the likely cause instead of a bare "no JSON array" (Entry 28).
        # The model returning prose is usually it declining to fabricate rather
        # than a format slip — most often because it exhausted its search
        # budget mid-verification, which is the behavior the prompt asks for.
        # A generic error sent me looking at the parser instead of the cap.
        low = text.lower()
        if any(s in low for s in ("search", "limit", "cannot verify",
                                 "without opening", "unverified")):
            raise ValueError(
                "curation returned prose, not JSON — the model appears to have "
                "declined to guess rather than fabricate references (often the "
                f"web-search budget, {config.curation_search_budget(batch)} for "
                f"a batch of {batch}). Its own explanation is stored "
                "in the curation_runs ledger row; read it before re-running.")
        raise ValueError("no JSON array in curation response")
    candidates = json.loads(m.group(1))
    required = {"title", "source_class", "source_ref", "license_class", "evidence"}
    for c in candidates:
        missing = required - c.keys()
        if missing:
            raise ValueError(f"candidate {c.get('title')!r} missing {missing}")
    return candidates


def run_curation(conn, channel=None, batch: int = config.CURATION_BATCH_SIZE,
                 verify_refs: bool = True) -> list[dict]:
    """One curation batch → candidates list + a curation_runs ledger row (R11)."""
    channel = channel or db.active_channel(conn)
    client = config.anthropic_client()
    model = db.effective_curation_model(conn)  # R14: Grace's setting or config

    prompt = build_prompt(channel, db.known_titles(conn), batch)
    messages = [{"role": "user", "content": prompt}]
    searches = in_tok = out_tok = cache_read = cache_write = 0
    turns = 0
    response = None
    for turns in range(1, config.CURATION_MAX_TURNS + 1):
        with client.messages.stream(
            model=model,
            max_tokens=16000,
            # Cost lever (Entry 28). This loop re-sends the WHOLE accumulated
            # transcript on every pause turn, and web-search results are large
            # input. Uncached, a 6-search batch re-reads them at full price
            # several times over — that was most of the $1.55. Top-level
            # cache_control auto-places the breakpoint on the last cacheable
            # block, i.e. the end of the turn just appended, which is exactly
            # the multi-turn pattern: each turn re-reads the prior prefix at
            # 0.1x instead of 1.0x.
            cache_control={"type": "ephemeral"},
            # Curation is search-and-list. Adaptive thinking is ON BY DEFAULT on
            # Sonnet 5 and effort defaults to `high`, so not setting this was
            # buying deep reasoning for a listing task.
            output_config={"effort": config.CURATION_EFFORT},
            tools=[{"type": "web_search_20260209", "name": "web_search",
                    "max_uses": config.curation_search_budget(batch)}],
            messages=messages,
        ) as stream:
            response = stream.get_final_message()
        in_tok += response.usage.input_tokens
        out_tok += response.usage.output_tokens
        cache_read += response.usage.cache_read_input_tokens or 0
        cache_write += response.usage.cache_creation_input_tokens or 0
        if response.usage.server_tool_use:
            searches += response.usage.server_tool_use.web_search_requests or 0
        if response.stop_reason == "pause_turn":
            # accumulate paused content: on a second pause the earlier turn's
            # search results must stay in the transcript, not be replaced
            if messages[-1]["role"] == "assistant":
                messages[-1]["content"] = list(messages[-1]["content"]) + \
                    list(response.content)
            else:
                messages.append({"role": "assistant", "content": response.content})
            print(f"[curate] pause {turns}/{config.CURATION_MAX_TURNS} "
                  f"({searches} searches so far)")
            continue
        break
    else:
        # Cap reached while still pausing. The ledger row below still records
        # every token spent — an aborted run must never be free-looking.
        print(f"[curate] WARNING: hit CURATION_MAX_TURNS="
              f"{config.CURATION_MAX_TURNS} and the model was still paused. "
              "Spend is recorded; raise the cap or lower the batch size.")

    # ledger row FIRST (R11): the spend is real even if the response is
    # unparseable — parse failures must not make cost invisible
    price_in, price_out = config.model_pricing(model)  # honors intro pricing
    cost = (in_tok / 1e6 * price_in
            + cache_read / 1e6 * price_in * config.CACHE_READ_MULTIPLIER
            + cache_write / 1e6 * price_in * config.CACHE_WRITE_MULTIPLIER
            + out_tok / 1e6 * price_out
            + searches * config.WEB_SEARCH_COST)
    text = "\n".join(b.text for b in (response.content if response else [])
                     if b.type == "text")
    run_id = conn.execute(
        "INSERT INTO curation_runs(channel_id, model, cost_usd, searches, "
        "candidates_json, input_tokens, output_tokens, cache_read_tokens, "
        "cache_write_tokens) VALUES(?,?,?,?,?,?,?,?,?)",
        (channel["id"], model, round(cost, 4), searches,
         json.dumps({"unparsed": text[:20000]}, ensure_ascii=False),
         in_tok, out_tok, cache_read, cache_write)).lastrowid
    conn.commit()

    candidates = parse_candidates(text, batch)
    # Verify references mechanically before they reach the pool (Entry 25).
    # Free — HTTP only — and it runs the same fetch/clean gates the worker
    # will, so the pool never promises a story ingest would reject.
    if verify_refs:
        print(f"[curate] verifying {len(candidates)} references (no API cost)…")
        candidates = verify.annotate(candidates)
    conn.execute("UPDATE curation_runs SET candidates_json=? WHERE id=?",
                 (json.dumps(candidates, ensure_ascii=False), run_id))
    conn.commit()
    usable = sum(1 for c in candidates if c.get("verified") is not False)
    cached_pct = (100 * cache_read / (in_tok + cache_read + cache_write)
                  if (in_tok + cache_read + cache_write) else 0)
    print(f"[curate] {len(candidates)} candidates ({usable} usable), "
          f"{searches} searches, ${cost:.3f} ({model})")
    print(f"[curate] tokens: {in_tok:,} in · {out_tok:,} out · "
          f"{cache_read:,} cache-read ({cached_pct:.0f}% of input served from "
          f"cache) · {cache_write:,} cache-write")
    return candidates
