#!/usr/bin/env python3
"""Probe 1: Kokoro on this Mac — installs? speed (× realtime)? quality on horror prose
(≥2 min for Grace to hear)? one non-English sample (channels amendment)?

Throwaway code — no authority after Phase 1.
Run: .venv/bin/python probe1_kokoro.py
Outputs: data/interim/probe1/horror_usher.wav, spanish_quiroga.wav + timings on stdout.
"""
import pathlib
import time

import numpy as np
import soundfile as sf

OUT = pathlib.Path(__file__).resolve().parents[1] / "data" / "interim" / "probe1"
OUT.mkdir(parents=True, exist_ok=True)
SR = 24000

# Public domain: Poe, "The Fall of the House of Usher" (1839), opening — ~430 words,
# should give ≥2.5 min of narration.
HORROR = """
During the whole of a dull, dark, and soundless day in the autumn of the year, when the
clouds hung oppressively low in the heavens, I had been passing alone, on horseback,
through a singularly dreary tract of country; and at length found myself, as the shades
of the evening drew on, within view of the melancholy House of Usher. I know not how it
was — but, with the first glimpse of the building, a sense of insufferable gloom pervaded
my spirit. I say insufferable; for the feeling was unrelieved by any of that half-pleasurable,
because poetic, sentiment, with which the mind usually receives even the sternest natural
images of the desolate or terrible. I looked upon the scene before me — upon the mere house,
and the simple landscape features of the domain — upon the bleak walls — upon the vacant
eye-like windows — upon a few rank sedges — and upon a few white trunks of decayed trees —
with an utter depression of soul which I can compare to no earthly sensation more properly
than to the after-dream of the reveller upon opium — the bitter lapse into every-day life —
the hideous dropping off of the veil. There was an iciness, a sinking, a sickening of the
heart — an unredeemed dreariness of thought which no goading of the imagination could
torture into aught of the sublime. What was it — I paused to think — what was it that so
unnerved me in the contemplation of the House of Usher? It was a mystery all insoluble;
nor could I grapple with the shadowy fancies that crowded upon me as I pondered. I was
forced to fall back upon the unsatisfactory conclusion, that while, beyond doubt, there
are combinations of very simple natural objects which have the power of thus affecting us,
still the analysis of this power lies among considerations beyond our depth. It was
possible, I reflected, that a mere different arrangement of the particulars of the scene,
of the details of the picture, would be sufficient to modify, or perhaps to annihilate
its capacity for sorrowful impression; and, acting upon this idea, I reined my horse to
the precipitous brink of a black and lurid tarn that lay in unruffled lustre by the
dwelling, and gazed down — but with a shudder even more thrilling than before — upon the
remodelled and inverted images of the gray sedge, and the ghastly tree-stems, and the
vacant and eye-like windows.
""".strip()

# Public domain: Horacio Quiroga, "El almohadón de plumas" (1907), opening.
SPANISH = """
Su luna de miel fue un largo escalofrío. Rubia, angelical y tímida, el carácter duro de
su marido heló sus soñadas niñerías de novia. Ella lo quería mucho, sin embargo, a veces
con un ligero estremecimiento cuando volviendo de noche juntos por la calle, echaba una
furtiva mirada a la alta estatura de Jordán, mudo desde hacía una hora. Él, por su parte,
la amaba profundamente, sin darlo a conocer.
""".strip()


def synth(pipeline, text, voice, path):
    t0 = time.perf_counter()
    chunks = [audio for _, _, audio in pipeline(text, voice=voice)]
    wall = time.perf_counter() - t0
    audio = np.concatenate([c.numpy() if hasattr(c, "numpy") else np.asarray(c) for c in chunks])
    dur = len(audio) / SR
    sf.write(path, audio, SR)
    print(f"  {path.name}: audio={dur:6.1f}s wall={wall:6.1f}s -> {dur/wall:4.1f}x realtime "
          f"({len(chunks)} chunks)")
    return dur, wall


if __name__ == "__main__":
    from kokoro import KPipeline

    t0 = time.perf_counter()
    en = KPipeline(lang_code="a")  # American English
    print(f"EN pipeline ready in {time.perf_counter()-t0:.1f}s (incl. any model download)")
    # warm-up (first call includes voice-pack load); excluded from the speed number
    for _ in en("Warm up.", voice="af_heart"):
        pass
    print("[horror prose, voice af_heart]")
    synth(en, HORROR, "af_heart", OUT / "horror_usher_af_heart.wav")
    print("[same text, deeper male voice am_michael for comparison]")
    synth(en, HORROR, "am_michael", OUT / "horror_usher_am_michael.wav")

    t0 = time.perf_counter()
    es = KPipeline(lang_code="e")  # Spanish
    print(f"ES pipeline ready in {time.perf_counter()-t0:.1f}s")
    print("[Spanish sample, voice ef_dora]")
    synth(es, SPANISH, "ef_dora", OUT / "spanish_quiroga_ef_dora.wav")
