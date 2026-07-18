#!/usr/bin/env python3
"""Probe 6: OpenAI TTS fallback — one-call render of one paragraph; cost recorded.
Requires OPENAI_API_KEY in ../.env.

Throwaway code — no authority after Phase 1.
Run: .venv/bin/python probe6_openai_tts.py
"""
import pathlib

ENV = pathlib.Path(__file__).resolve().parents[1] / ".env"
OUT = pathlib.Path(__file__).resolve().parents[1] / "data" / "interim" / "probe6"

# Same Usher opening paragraph as probe 2, for a direct quality comparison with Kokoro.
PARA = ("During the whole of a dull, dark, and soundless day in the autumn of the year, "
        "when the clouds hung oppressively low in the heavens, I had been passing alone, "
        "on horseback, through a singularly dreary tract of country; and at length found "
        "myself, as the shades of the evening drew on, within view of the melancholy "
        "House of Usher.")


def load_env():
    env = {}
    for line in ENV.read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


if __name__ == "__main__":
    from openai import OpenAI

    key = load_env().get("OPENAI_API_KEY")
    assert key, f"OPENAI_API_KEY not found in {ENV}"
    client = OpenAI(api_key=key)
    OUT.mkdir(parents=True, exist_ok=True)

    path = OUT / "usher_openai_tts.mp3"
    resp = client.audio.speech.create(model="gpt-4o-mini-tts", voice="onyx", input=PARA)
    resp.write_to_file(path)

    # gpt-4o-mini-tts ≈ $12/M input chars (~$0.015/min audio); tts-1 is $15/M chars
    chars = len(PARA)
    print(f"rendered {chars} chars -> {path} ({path.stat().st_size} bytes)")
    print(f"est cost this call: ${chars / 1e6 * 12:.5f}; full 30-min story (~27k chars): "
          f"~${27000 / 1e6 * 12:.2f}")
