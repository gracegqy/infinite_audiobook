"""Curation stage (DESIGN §5): Messages API + web_search against the standing
reputation bar + active channel criteria. Model is fixed config — never
auto-escalated (R14)."""
import json
import re

from . import config, db, taste, verify

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

# Selection prompt (free_llm mode, Entry 32). The model never names a story and
# never supplies a reference — it returns INDICES into a list the pipeline
# built from free sources. A hallucinated ref is therefore not mitigated, it is
# impossible: every field except the rationale comes from the source adapter.
# No web search tool is attached, which is where ~half the paid path's cost went.
SELECTION_TEMPLATE = """You are the curator for a private read-aloud fiction \
library (single listener, personal use).

Below are {n} candidate stories the pipeline already found and length-checked.
Choose the {batch} BEST for this channel:
- Genre: {genre}
- Language: {language}
- Topics/themes: {topics}
- Era: {era}
- Avoid: {avoid}
- Extra criteria: {extra}

Judge on literary quality and how well each fits the criteria above, using what
you know of these works. You have no web access here — if you do not recognise a
title, judge it on its stated reputation evidence and length, and say so in your
reason rather than inventing a claim about it.
{balance}
CANDIDATES:
{listing}

Return ONLY a JSON array of {ask} objects, BEST FIRST, no prose around it:
[{{"i": <index from the list above>, "why": "<one sentence>"}}, ...]
Use each index at most once. Never invent an index that is not listed.
Rank {ask} rather than {batch}: some references fail a mechanical length check
afterwards, and the extras replace them without another round."""

BALANCE_CLAUSE = """
BALANCE: the list mixes {classes}. Rank good picks from EACH kind — the pipeline
enforces the final split itself, so ranking only one kind just wastes your picks.
"""

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
                 verify_refs: bool = True,
                 taste_profile: str | None = None) -> list[dict]:
    """One curation batch → candidates list + a curation_runs ledger row (R11)."""
    channel = channel or db.active_channel(conn)
    client = config.anthropic_client()
    model = db.effective_curation_model(conn)  # R14: Grace's setting or config

    if taste_profile is None:  # None = "work it out"; "" = "deliberately none"
        taste_profile = taste.profile_for(conn, channel["id"])
    prompt = build_prompt(channel, db.known_titles(conn), batch,
                          taste_profile=taste_profile)
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
    run_id = db.record_curation_run(
        conn, channel["id"], model, cost, searches,
        json.dumps({"unparsed": text[:20000]}, ensure_ascii=False),
        in_tok, out_tok, cache_read, cache_write,
        taste_profile_text=taste_profile)

    candidates = parse_candidates(text, batch)
    # Verify references mechanically before they reach the pool (Entry 25).
    # Free — HTTP only — and it runs the same fetch/clean gates the worker
    # will, so the pool never promises a story ingest would reject.
    if verify_refs:
        print(f"[curate] verifying {len(candidates)} references (no API cost)…")
        candidates = verify.annotate(candidates)
    db.update_curation_candidates(
        conn, run_id, json.dumps(candidates, ensure_ascii=False))
    usable = sum(1 for c in candidates if c.get("verified") is not False)
    cached_pct = (100 * cache_read / (in_tok + cache_read + cache_write)
                  if (in_tok + cache_read + cache_write) else 0)
    print(f"[curate] {len(candidates)} candidates ({usable} usable), "
          f"{searches} searches, ${cost:.3f} ({model})")
    print(f"[curate] tokens: {in_tok:,} in · {out_tok:,} out · "
          f"{cache_read:,} cache-read ({cached_pct:.0f}% of input served from "
          f"cache) · {cache_write:,} cache-write")
    return candidates


# ---- free_llm selection (Entry 32): taste over a supplied list, no search ----

def apply_class_quotas(candidates: list[dict], batch: int,
                       floor: int | None = None) -> list[dict]:
    """Re-order the model's ranked picks so the FIRST `batch` give every source
    class at least `floor` places, then follow the model's ranking for the rest.
    The remainder are kept behind them as spares.

    Balance is enforced here, in code, and not asked for in the prompt. Entries
    27-28 spent two paid batches and two prompt rewrites discovering that a
    model told to balance will still return what it recognises best — the first
    free_llm run came back 9 Gutenberg / 3 creepypasta off a 36/36 shortlist.
    The model is good at ranking within a kind; it should not also be trusted to
    hold a ratio.

    A FLOOR, not an even split (Grace's ruling, Entry 35). The even split shipped
    in Entry 32 also pinned the one axis her ratings are clearest on — she rates
    classics 5.0 and creepypasta 2.0 (n=3), the model already ranked gutenberg
    ~2:1, and the round-robin pulled it back to 1:1 every time, which is why the
    Phase 6 gate could detect no effect (Entry 34). The floor keeps what Entry 32
    was actually protecting — no class is ever starved to zero — while letting
    the ranking, and so the taste profile behind it, decide the remaining slots.

    Nothing is discarded: a class with fewer than `floor` picks yields its unused
    places to the next-ranked candidates.
    """
    if floor is None:
        floor = config.CLASS_FLOOR
    buckets: dict[str, list[dict]] = {}
    for c in candidates:
        buckets.setdefault(c.get("source_class") or "?", []).append(c)
    if len(buckets) < 2:
        return list(candidates)

    # A floor that cannot fit degrades to the largest one that can, rather than
    # silently over-filling the batch or starving the last class.
    per_class = min(floor, batch // len(buckets))

    head, taken = [], set()
    for bucket in buckets.values():             # the guaranteed minimum
        for c in bucket[:per_class]:
            head.append(c)
            taken.add(id(c))
    # …then the model's ranking decides the rest, unconstrained.
    for c in candidates:
        if len(head) >= batch:
            break
        if id(c) not in taken:
            head.append(c)
            taken.add(id(c))
    tail = [c for c in candidates if id(c) not in taken]  # spares, rank order
    return head + tail


def build_selection_prompt(channel, candidates: list[dict], batch: int,
                           ask: int | None = None,
                           taste_profile: str | None = None) -> str:
    classes = sorted({c.get("source_class") or "?" for c in candidates})
    listing = "\n".join(
        f"[{i}] {c['title']}"
        + (f" — {c['author']}" if c.get("author") else "")
        + f" ({c.get('source_class')}"
        + (f", {c['evidence'][0]}" if c.get("evidence") else "")
        + ")"
        for i, c in enumerate(candidates))
    prompt = SELECTION_TEMPLATE.format(
        n=len(candidates), batch=batch, ask=ask or batch,
        genre=channel["genre"] or "any",
        language=channel["language"],
        topics=", ".join(channel_list_field(channel, "topics_json")) or "any",
        era=channel["era"] or "any",
        avoid=", ".join(channel_list_field(channel, "exclusions_json")) or "nothing",
        extra=channel["extra_criteria"] or "none",
        balance=(BALANCE_CLAUSE.format(classes=" and ".join(classes))
                 if len(classes) > 1 else ""),
        listing=listing)
    # Phase 6. Appended AFTER the criteria and the listing, in the same shape
    # build_prompt uses, so both curation paths present taste identically.
    if taste_profile:
        prompt += f"\n\nLISTENER TASTE PROFILE (weight your picks):\n{taste_profile}"
    return prompt


def parse_selection(text: str, n: int, batch: int) -> list[tuple[int, str]]:
    """[(index, why)] — every index validated against the list that was sent.
    An out-of-range index is dropped rather than trusted: it is the one way this
    mode could still point at something that does not exist."""
    m = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.S) or \
        re.search(r"(\[\s*\{.*\}\s*\])", text, re.S)
    if not m:
        raise ValueError(
            "selection returned prose, not JSON — its text is stored in the "
            "curation_runs ledger row; read it before re-running.")
    out, seen = [], set()
    for item in json.loads(m.group(1)):
        try:
            i = int(item["i"])
        except (KeyError, TypeError, ValueError):
            continue
        if not (0 <= i < n) or i in seen:
            continue
        seen.add(i)
        out.append((i, str(item.get("why") or "").strip()))
    return out[:batch]


def run_selection(conn, channel, candidates: list[dict], batch: int,
                  log=print, taste_profile: str | None = None
                  ) -> tuple[list[dict], int]:
    """(chosen candidates, ledger run id). One zero-search selection call over
    `candidates`. Writes its own R11
    ledger row like every other pool build. On any failure the free candidates
    are returned in source order — degrading to the $0 path is safe because
    every candidate is already real and length-checked, but it is logged and
    stamped on the candidates rather than passed off as a successful pick."""
    client = config.anthropic_client()
    model = db.effective_curation_model(conn)
    ask = min(len(candidates), batch + config.SELECTION_SPARES)
    if taste_profile is None:  # None = "work it out"; "" = "deliberately none"
        taste_profile = taste.profile_for(conn, channel["id"])
    prompt = build_selection_prompt(channel, candidates, batch, ask=ask,
                                    taste_profile=taste_profile)

    response = client.messages.create(
        model=model,
        max_tokens=config.SELECTION_MAX_TOKENS,
        # No `tools`: the whole point of this mode is that search is unnecessary
        # once the sources supply verified references.
        output_config={"effort": config.SELECTION_EFFORT},
        messages=[{"role": "user", "content": prompt}],
    )
    u = response.usage
    in_tok, out_tok = u.input_tokens, u.output_tokens
    cache_read = u.cache_read_input_tokens or 0
    cache_write = u.cache_creation_input_tokens or 0
    price_in, price_out = config.model_pricing(model)
    cost = (in_tok / 1e6 * price_in
            + cache_read / 1e6 * price_in * config.CACHE_READ_MULTIPLIER
            + cache_write / 1e6 * price_in * config.CACHE_WRITE_MULTIPLIER
            + out_tok / 1e6 * price_out)
    text = "\n".join(b.text for b in response.content if b.type == "text")

    run_id = db.record_curation_run(
        conn, channel["id"], model, cost, 0,
        json.dumps({"unparsed": text[:20000]}, ensure_ascii=False),
        in_tok, out_tok, cache_read, cache_write,
        taste_profile_text=taste_profile)

    try:
        picks = parse_selection(text, len(candidates), ask)
    except ValueError as e:
        log(f"[select] WARNING: {e}")
        picks = []
    if picks:
        chosen = []
        for i, why in picks:
            c = dict(candidates[i])
            if why:
                c["selection_note"] = why
            chosen.append(c)
        chosen = apply_class_quotas(chosen, batch)
    else:
        log(f"[select] falling back to source order — no usable picks. "
            f"Cost ${cost:.4f} is still recorded (ledger row {run_id}).")
        chosen = [dict(c) for c in candidates[:ask]]
        for c in chosen:
            c["unverified"] = list(c.get("unverified") or []) + [
                "model selection failed; this candidate was taken in source "
                "order, so no taste judgement was applied"]

    mix = {}
    for c in chosen[:batch]:
        mix[c.get("source_class") or "?"] = mix.get(c.get("source_class") or "?", 0) + 1
    log(f"[select] taste profile: "
        + (f"{len(taste_profile.splitlines())} lines applied"
           if taste_profile else "none (too few ratings — see "
                                 "config.TASTE_MIN_RATED_STORIES)"))
    log(f"[select] {len(chosen)} ranked ({len(candidates)} offered), "
        f"top {batch} = " + ", ".join(f"{n} {k}" for k, n in sorted(mix.items()))
        + f"; 0 searches, ${cost:.4f} ({model})")
    log(f"[select] tokens: {in_tok:,} in · {out_tok:,} out")
    return chosen, run_id


# ---- spend guard (Entry 33) ----

def estimate_cost(model: str, batch: int) -> tuple[float, str]:
    """(estimated $, how it was derived) for a paid `llm` batch.

    Deliberately rough and deliberately stated. Search fees are exact — the
    budget is a hard cap and a batch of any size tends to use it. Tokens are
    scaled from run 4's measured split (Entry 28: 212,191 input at 93% cached,
    ~8,900 output for a batch of 8), which is the only cached run there is.
    Being approximate is fine; being SILENT is what went wrong before.
    """
    searches = config.curation_search_budget(batch)
    fees = searches * config.WEB_SEARCH_COST
    price_in, price_out = config.model_pricing(model)
    scale = batch / config.CURATION_BATCH_SIZE
    # cached input: 212k tokens at run 4's 93% cache-read ratio
    in_cost = (212_191 * scale / 1e6) * price_in * (
        0.93 * config.CACHE_READ_MULTIPLIER + 0.07)
    out_cost = (8_900 * scale / 1e6) * price_out
    total = fees + in_cost + out_cost
    return total, (f"{searches} searches x ${config.WEB_SEARCH_COST:.2f} = "
                   f"${fees:.2f} in fees, plus ~${in_cost + out_cost:.2f} of "
                   f"tokens scaled from run 4 for a batch of {batch}")


def confirm_spend(model: str, batch: int, approved: bool,
                  log=print) -> bool:
    """True when a paid build may proceed. Prints the estimate either way."""
    total, how = estimate_cost(model, batch)
    log(f"[curate] estimated cost: ${total:.2f} ({how})")
    if total <= config.CURATION_SPEND_CONFIRM_USD or approved:
        return True
    log(f"[curate] ABORTED: estimate exceeds "
        f"${config.CURATION_SPEND_CONFIRM_USD:.2f}. Re-run with --yes-spend to "
        f"approve, switch to a free mode in Settings, or lower "
        f"config.POOL_BATCH_SIZE.")
    return False
