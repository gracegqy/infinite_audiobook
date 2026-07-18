"""Curation stage (DESIGN §5): Messages API + web_search against the standing
reputation bar + active channel criteria. Model is fixed config — never
auto-escalated (R14)."""
import json
import re

from . import config, db

PROMPT_TEMPLATE = """You are the curator for a private read-aloud fiction library \
(single listener, personal use).

Find {batch} highly-reputed SHORT stories (standalone works under ~15,000 words —
not novels, not multi-story collections) matching ALL channel criteria:
- Genre: {genre}
- Language: {language}
- Extra criteria: {extra}

REPUTATION BAR (channel-independent): every candidate must carry checkable evidence —
a NAMED list, essay, award, ranking, or ratings page that vouches for it (e.g. "NPR's
100 Best Horror list", "Gutenberg top-100 downloads"). No vague "widely considered".
Use web search to verify evidence rather than relying on memory. If you could not
verify a claim, flag it honestly in "unverified".

SOURCING: prefer texts available as {source_hint}. For Gutenberg candidates the
ebook id MUST be a standalone edition containing ONLY that story — collection
volumes ("The Works of...", "Complete Tales...") are rejected by the pipeline;
verify the ebook is the single story, and skip candidates that only exist in
collections. Do NOT propose any of these already-known titles:
{exclusions}

Return ONLY a JSON array (no prose around it), each element:
{{"title": str, "author": str, "year": int or null,
  "source_class": "gutenberg"|"creepypasta",
  "source_ref": "<Gutenberg ebook id number>"|"<creepypasta wiki page title>",
  "license_class": "pd"|"modern_private",
  "evidence": [str, ...], "unverified": [str, ...]}}"""

SOURCE_HINTS = {
    "en": "Project Gutenberg plain text (public domain) or creepypasta-wiki pages",
    "fr": "Project Gutenberg plain text (French-language public domain)",
    "zh": "Project Gutenberg plain text (Chinese-language public domain)",
}


def build_prompt(channel, known_titles: list[str],
                 batch: int = config.CURATION_BATCH_SIZE,
                 taste_profile: str | None = None) -> str:
    prompt = PROMPT_TEMPLATE.format(
        batch=batch,
        genre=channel["genre"] or "any",
        language=channel["language"],
        extra=channel["extra_criteria"] or "none",
        source_hint=SOURCE_HINTS.get(channel["language"], SOURCE_HINTS["en"]),
        exclusions="\n".join(f"- {t}" for t in known_titles) or "(none yet)",
    )
    if taste_profile:  # Phase 6
        prompt += f"\n\nLISTENER TASTE PROFILE (weight your picks):\n{taste_profile}"
    return prompt


def parse_candidates(text: str) -> list[dict]:
    """Extract the JSON array from the response (tolerates a ```json fence).
    The unfenced fallback anchors on "[{" ... "}]" so brackets in surrounding
    prose ("[NPR list]") can't poison the match."""
    m = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.S) or \
        re.search(r"(\[\s*\{.*\}\s*\])", text, re.S)
    if not m:
        raise ValueError("no JSON array in curation response")
    candidates = json.loads(m.group(1))
    required = {"title", "source_class", "source_ref", "license_class", "evidence"}
    for c in candidates:
        missing = required - c.keys()
        if missing:
            raise ValueError(f"candidate {c.get('title')!r} missing {missing}")
    return candidates


def run_curation(conn, channel=None, batch: int = config.CURATION_BATCH_SIZE) -> list[dict]:
    """One curation batch → candidates list + a curation_runs ledger row (R11)."""
    channel = channel or db.active_channel(conn)
    client = config.anthropic_client()

    prompt = build_prompt(channel, db.known_titles(conn), batch)
    messages = [{"role": "user", "content": prompt}]
    searches = in_tok = out_tok = 0
    while True:
        with client.messages.stream(
            model=config.CURATION_MODEL,
            max_tokens=16000,
            tools=[{"type": "web_search_20260209", "name": "web_search",
                    "max_uses": config.CURATION_MAX_SEARCHES}],
            messages=messages,
        ) as stream:
            response = stream.get_final_message()
        in_tok += response.usage.input_tokens
        out_tok += response.usage.output_tokens
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
            continue
        break

    # ledger row FIRST (R11): the spend is real even if the response is
    # unparseable — parse failures must not make cost invisible
    price_in, price_out = config.MODEL_PRICING[config.CURATION_MODEL]
    cost = (in_tok / 1e6 * price_in + out_tok / 1e6 * price_out
            + searches * config.WEB_SEARCH_COST)
    text = "\n".join(b.text for b in response.content if b.type == "text")
    run_id = conn.execute(
        "INSERT INTO curation_runs(channel_id, model, cost_usd, searches, candidates_json) "
        "VALUES(?,?,?,?,?)",
        (channel["id"], config.CURATION_MODEL, round(cost, 4), searches,
         json.dumps({"unparsed": text[:20000]}, ensure_ascii=False))).lastrowid
    conn.commit()

    candidates = parse_candidates(text)
    conn.execute("UPDATE curation_runs SET candidates_json=? WHERE id=?",
                 (json.dumps(candidates, ensure_ascii=False), run_id))
    conn.commit()
    print(f"[curate] {len(candidates)} candidates, {searches} searches, ${cost:.3f} "
          f"({config.CURATION_MODEL})")
    return candidates
