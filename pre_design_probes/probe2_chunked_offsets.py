#!/usr/bin/env python3
"""Probe 2: per-paragraph synthesis + concatenation.
Questions (TASKS.md §1.2): audible seams? do computed offsets match the concatenated
audio within ~100 ms?

Method: synthesize 6 consecutive Usher paragraphs separately; record each chunk's
duration; concatenate (variant A: raw butt-join; variant B: 200 ms silence joins);
offsets = cumulative durations. Verify offsets against the concatenated file by
construction check (sample counts) AND an independent energy check: at each offset in
variant B, the preceding 150 ms should be near-silence (the inserted gap), which fails
loudly if offsets drift. Grace listens to variant A for seams.

Throwaway code — no authority after Phase 1.
"""
import json
import pathlib

import numpy as np
import soundfile as sf

OUT = pathlib.Path(__file__).resolve().parents[1] / "data" / "interim" / "probe2"
OUT.mkdir(parents=True, exist_ok=True)
SR = 24000
GAP_S = 0.2

PARAS = [
    "During the whole of a dull, dark, and soundless day in the autumn of the year, when the clouds hung oppressively low in the heavens, I had been passing alone, on horseback, through a singularly dreary tract of country.",
    "At length I found myself, as the shades of the evening drew on, within view of the melancholy House of Usher. I know not how it was, but with the first glimpse of the building, a sense of insufferable gloom pervaded my spirit.",
    "I looked upon the scene before me, upon the mere house, and the simple landscape features of the domain, upon the bleak walls, upon the vacant eye-like windows, upon a few rank sedges, and upon a few white trunks of decayed trees.",
    "There was an iciness, a sinking, a sickening of the heart, an unredeemed dreariness of thought which no goading of the imagination could torture into aught of the sublime.",
    "What was it, I paused to think, what was it that so unnerved me in the contemplation of the House of Usher? It was a mystery all insoluble.",
    "I reined my horse to the precipitous brink of a black and lurid tarn that lay in unruffled lustre by the dwelling, and gazed down upon the remodelled and inverted images of the gray sedge, and the ghastly tree-stems, and the vacant and eye-like windows.",
]


def rms_db(x):
    r = float(np.sqrt(np.mean(x ** 2))) if len(x) else 0.0
    return -120.0 if r <= 0 else 20 * np.log10(r)


if __name__ == "__main__":
    from kokoro import KPipeline

    en = KPipeline(lang_code="a")
    for _ in en("Warm up.", voice="af_heart"):
        pass

    chunks = []
    for i, p in enumerate(PARAS):
        audio = np.concatenate([a.numpy() if hasattr(a, "numpy") else np.asarray(a)
                                for _, _, a in en(p, voice="af_heart")])
        chunks.append(audio)
        print(f"  para {i}: {len(audio)/SR:6.2f}s  tail_rms={rms_db(audio[-int(0.05*SR):]):6.1f} dB")

    # Variant A: butt join; offsets purely from cumulative chunk lengths
    concat_a = np.concatenate(chunks)
    offsets_a = np.cumsum([0] + [len(c) for c in chunks[:-1]]) / SR
    sf.write(OUT / "concat_A_buttjoin.wav", concat_a, SR)

    # Variant B: 200 ms silence between paragraphs
    gap = np.zeros(int(GAP_S * SR), dtype=concat_a.dtype)
    parts, offsets_b, pos = [], [], 0
    for i, c in enumerate(chunks):
        offsets_b.append(pos / SR)
        parts.append(c)
        pos += len(c)
        if i < len(chunks) - 1:
            parts.append(gap)
            pos += len(gap)
    concat_b = np.concatenate(parts)
    sf.write(OUT / "concat_B_200ms_gaps.wav", concat_b, SR)

    manifest = {"sr": SR, "gap_s": GAP_S,
                "offsets_a": [round(float(o), 4) for o in offsets_a],
                "offsets_b": [round(float(o), 4) for o in offsets_b],
                "durations": [round(len(c) / SR, 4) for c in chunks]}
    (OUT / "offsets.json").write_text(json.dumps(manifest, indent=2))

    # Round-trip check on the manifest shape
    assert json.loads(json.dumps(manifest)) == manifest, "manifest round-trip failed"

    # Independent offset check in variant B: window just before each offset (inside the
    # inserted gap) must be silent; window just after must have speech-level energy.
    print("\n[offset verification, variant B]")
    ok = True
    for i, o in enumerate(offsets_b):
        s = int(o * SR)
        pre = concat_b[max(0, s - int(0.15 * SR)):s]
        post = concat_b[s:s + int(0.5 * SR)]
        pre_db, post_db = rms_db(pre), rms_db(post)
        verdict = "OK" if (i == 0 or pre_db < -50) and post_db > -45 else "FAIL"
        ok &= verdict == "OK"
        print(f"  offset {i} @{o:7.2f}s  pre(gap)={pre_db:6.1f} dB  post(speech)={post_db:6.1f} dB  {verdict}")

    # Construction check for variant A: last sample index == sum of chunk lengths
    assert len(concat_a) == sum(len(c) for c in chunks)
    print(f"\nVariant A construction check: concat len == sum(chunks) == {len(concat_a)} samples")
    print(f"RESULT: offsets {'verified' if ok else 'FAILED'}; listen to concat_A_buttjoin.wav for seams")
