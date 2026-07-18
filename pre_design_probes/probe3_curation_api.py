#!/usr/bin/env python3
"""Probe 3 (API half): can Claude + web search produce 10 horror candidates with
checkable reputation evidence and correct public-domain vs modern classification?

This exercises the exact mechanism the pipeline will use: Anthropic Messages API with
the server-side web_search tool. Signal-quality half already answered manually (see
probe_results.txt). Requires ANTHROPIC_API_KEY in ../.env.

Throwaway code — no authority after Phase 1.
Run: .venv/bin/python probe3_curation_api.py
"""
import pathlib

ENV = pathlib.Path(__file__).resolve().parents[1] / ".env"
OUT = pathlib.Path(__file__).resolve().parents[1] / "data" / "interim" / "probe3_candidates.md"

PROMPT = """You are the curator for a private read-aloud horror fiction library.
Find 10 highly-reputed horror short stories: 5 public-domain classics and 5 modern web
horror stories (r/NoSleep, creepypasta, or similar).

For EACH candidate give:
1. Title and author
2. Classification: PUBLIC DOMAIN (with publication year) or MODERN/AUTHOR-OWNED
3. Reputation evidence: name the specific list, essay, award, or ranking that vouches for
   it (e.g. "NPR's 100 Best Horror list", "won NoSleep's Scariest Story 2021") — searchable
   claims only, no vague "widely considered".
4. Where the clean text lives (Gutenberg ID / subreddit / wiki page).

Use web search to verify reputation evidence rather than relying on memory."""


def load_env():
    env = {}
    if ENV.exists():
        for line in ENV.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


if __name__ == "__main__":
    import anthropic

    key = load_env().get("ANTHROPIC_API_KEY")
    assert key, f"ANTHROPIC_API_KEY not found in {ENV}"
    client = anthropic.Anthropic(api_key=key)

    messages = [{"role": "user", "content": PROMPT}]
    searches = 0
    while True:
        with client.messages.stream(
            model="claude-opus-4-8",
            max_tokens=16000,
            thinking={"type": "adaptive"},
            tools=[{"type": "web_search_20260209", "name": "web_search", "max_uses": 12}],
            messages=messages,
        ) as stream:
            response = stream.get_final_message()
        if response.usage.server_tool_use:
            searches += response.usage.server_tool_use.web_search_requests or 0
        if response.stop_reason == "pause_turn":
            messages = [{"role": "user", "content": PROMPT},
                        {"role": "assistant", "content": response.content}]
            continue
        break

    text = "\n".join(b.text for b in response.content if b.type == "text")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text)
    u = response.usage
    # Opus 4.8: $5/M in, $25/M out; web search $10 per 1000 searches
    cost = u.input_tokens / 1e6 * 5 + u.output_tokens / 1e6 * 25 + searches * 0.01
    print(f"stop_reason={response.stop_reason}  in={u.input_tokens} out={u.output_tokens} "
          f"searches={searches}  est_cost=${cost:.3f}")
    print(f"candidates written to {OUT}")
