"""Render the voice-audition gallery samples (AMENDMENT_04 D2): one short
paragraph per voice in config.VOICE_OPTIONS, rendered ONCE into
data/voice_samples/<voice>.m4a — previews are then free forever.

Run: .venv/bin/python scripts/render_voice_samples.py [--only <voice>]
$0 for en/fr (Kokoro local); zh voices call the edge-tts cloud endpoint
(accepted caveat, DESIGN §5). Existing samples are skipped unless --force.
"""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from pipeline import config, synthesize  # noqa: E402

SAMPLE_TEXT = {
    "en": ("The house had been quiet for an hour when the knocking began — "
           "three slow raps from a room that held nothing at all."),
    "fr": ("La maison était silencieuse depuis une heure quand les coups "
           "commencèrent — trois lents frappements venus d'une pièce vide."),
    "zh": "屋子安静了一个小时，敲门声才响起来——从一间空无一物的房间里，传来三下缓慢的敲击。",
}


def main(argv: list[str]) -> int:
    force = "--force" in argv
    only = argv[argv.index("--only") + 1] if "--only" in argv else None
    config.VOICE_SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    failures = 0
    for language, voices in config.VOICE_OPTIONS.items():
        engine_name = config.TTS_BY_LANGUAGE[language][0]
        for voice in voices:
            if only and voice != only:
                continue
            out = config.VOICE_SAMPLES_DIR / f"{voice}.m4a"
            if out.exists() and not force:
                print(f"[samples] {voice}: exists, skipping")
                continue
            try:
                engine = synthesize.ENGINES[engine_name](language, voice)
                samples, sr = engine.render(SAMPLE_TEXT[language])
                synthesize._write_m4a(samples, sr, out)
                print(f"[samples] {voice}: OK ({len(samples) / sr:.1f}s -> {out})")
            except Exception as e:
                # one bad voice must not kill the gallery build
                failures += 1
                print(f"[samples] {voice}: FAILED ({e})")
    print(f"[samples] done, {failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
