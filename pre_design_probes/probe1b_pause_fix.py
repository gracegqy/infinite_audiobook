#!/usr/bin/env python3
"""Probe 1b: diagnose + fix the mid-sentence pauses Grace heard in probe 1/2 audio.

Hypothesis: the probe scripts' triple-quoted strings contain hard line-wraps; Kokoro's
KPipeline splits chunks on newlines, so every wrapped line ends in a chunk boundary
(padded with silence) mid-sentence. Same failure mode awaits the real pipeline:
Gutenberg plain text is hard-wrapped at ~70 cols.

Method: measure internal silence gaps (>250 ms) in the original render, re-synthesize
with whitespace-normalized text (newlines collapsed to spaces), measure again.
Throwaway code — no authority after Phase 1.
"""
import pathlib
import re
import time

import numpy as np
import soundfile as sf

from probe1_kokoro import HORROR, SPANISH  # reuse the exact same texts

OUT = pathlib.Path(__file__).resolve().parents[1] / "data" / "interim" / "probe1"
SR = 24000


def gaps(path, thresh_s=0.25, floor_db=-45):
    audio, sr = sf.read(path)
    win = int(0.02 * sr)
    n = len(audio) // win
    frames = audio[: n * win].reshape(n, win)
    rms = np.sqrt((frames ** 2).mean(axis=1))
    silent = rms < 10 ** (floor_db / 20)
    out, run = [], 0
    for i, s in enumerate(silent):
        run = run + 1 if s else 0
        if not s and run == 0:
            pass
    # find runs
    out = []
    i = 0
    while i < n:
        if silent[i]:
            j = i
            while j < n and silent[j]:
                j += 1
            dur = (j - i) * 0.02
            if dur >= thresh_s and i > 0 and j < n:  # internal only
                out.append((i * 0.02, dur))
            i = j
        else:
            i += 1
    return out


def synth(pipeline, text, voice, path):
    t0 = time.perf_counter()
    chunks = [a.numpy() if hasattr(a, "numpy") else np.asarray(a)
              for _, _, a in pipeline(text, voice=voice)]
    audio = np.concatenate(chunks)
    sf.write(path, audio, SR)
    print(f"    {path.name}: {len(audio)/SR:6.1f}s in {time.perf_counter()-t0:5.1f}s wall, "
          f"{len(chunks)} chunks")
    return path


def normalize(text):
    # collapse all whitespace runs (incl. hard line-wraps) to single spaces,
    # keeping nothing but sentence text — paragraph splitting happens upstream
    return re.sub(r"\s+", " ", text).strip()


if __name__ == "__main__":
    from kokoro import KPipeline

    print(f"[diagnosis] HORROR literal contains {HORROR.count(chr(10))} embedded newlines "
          f"(hard wraps) -> expected chunk-per-line splitting")
    for f in ["horror_usher_af_heart.wav", "horror_usher_am_michael.wav",
              "spanish_quiroga_ef_dora.wav"]:
        g = gaps(OUT / f)
        print(f"  {f}: {len(g)} internal gaps >=250ms; worst "
              f"{max((d for _, d in g), default=0):.2f}s")

    print("\n[fix] re-rendering with whitespace-normalized text")
    en = KPipeline(lang_code="a")
    for _ in en("Warm up.", voice="af_heart"):
        pass
    synth(en, normalize(HORROR), "af_heart", OUT / "horror_usher_af_heart_fixed.wav")
    synth(en, normalize(HORROR), "am_michael", OUT / "horror_usher_am_michael_fixed.wav")
    es = KPipeline(lang_code="e")
    synth(es, normalize(SPANISH), "ef_dora", OUT / "spanish_quiroga_ef_dora_fixed.wav")

    print("\n[verification] gaps after fix:")
    for f in ["horror_usher_af_heart_fixed.wav", "horror_usher_am_michael_fixed.wav",
              "spanish_quiroga_ef_dora_fixed.wav"]:
        g = gaps(OUT / f)
        print(f"  {f}: {len(g)} internal gaps >=250ms; worst "
              f"{max((d for _, d in g), default=0):.2f}s")
