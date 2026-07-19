"""Synthesize stage (DESIGN §5): per-paragraph render → butt-join concat →
64k AAC m4a via afconvert (wav interim deleted) → offsets manifest.

Engine is per-language config (config.TTS_BY_LANGUAGE). Degrade rule (binding,
§9.6): a primary-engine failure mid-story restarts the story on OpenAI TTS —
never a blocked queue. Offsets are exact by construction: every engine returns
PCM samples, durations are sample counts (probe 2)."""
import asyncio
import io
import subprocess
import tempfile
import pathlib

import numpy as np
import soundfile as sf

from . import config


class SynthesisError(Exception):
    pass


class AbortRender(Exception):
    """Story was skipped/read mid-render (AMENDMENT_04 C) — abort remaining
    paragraphs; never triggers the OpenAI fallback."""


def _to_np(chunk):
    return chunk.numpy() if hasattr(chunk, "numpy") else np.asarray(chunk)


def _mono(samples: np.ndarray) -> np.ndarray:
    """Downmix to mono — the single copy of this logic; both compressed-decode
    and cloud-TTS paths feed the sample-count duration math through it."""
    return samples.mean(axis=1) if samples.ndim > 1 else samples


class KokoroEngine:
    name = "kokoro"

    def __init__(self, language: str, voice: str):
        from kokoro import KPipeline
        self.voice = voice
        self.pipe = KPipeline(lang_code=config.KOKORO_LANG_CODES[language])
        for _ in self.pipe("Warm up.", voice=voice):
            pass

    def render(self, paragraph: str) -> tuple[np.ndarray, int]:
        chunks = [_to_np(a) for _, _, a in self.pipe(paragraph, voice=self.voice)]
        if not chunks:
            raise SynthesisError("kokoro returned no audio")
        return np.concatenate(chunks), config.SAMPLE_RATE


def decode_audio_bytes(data: bytes, suffix: str) -> tuple[np.ndarray, int]:
    """Compressed bytes (mp3 from edge-tts / cloud TTS) → PCM samples via
    afconvert. Sample-count durations keep offsets exact for non-wav engines
    (DESIGN §5 — the duration-read path under unit test)."""
    config.INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=config.INTERIM_DIR) as td:
        src = pathlib.Path(td) / f"in{suffix}"
        dst = pathlib.Path(td) / "out.wav"
        src.write_bytes(data)
        proc = subprocess.run(
            ["afconvert", "-f", "WAVE", "-d", "LEI16", str(src), str(dst)],
            capture_output=True, text=True)
        if proc.returncode != 0:
            raise SynthesisError(f"afconvert decode failed: {proc.stderr.strip()}")
        samples, sr = sf.read(dst, dtype="float32")
        return _mono(samples), sr


class EdgeTTSEngine:
    name = "edge_tts"

    def __init__(self, language: str, voice: str):
        self.voice = voice

    def render(self, paragraph: str) -> tuple[np.ndarray, int]:
        import edge_tts

        async def synth():
            buf = io.BytesIO()
            communicate = edge_tts.Communicate(paragraph, self.voice)
            async for msg in communicate.stream():
                if msg["type"] == "audio":
                    buf.write(msg["data"])
            return buf.getvalue()

        try:
            data = asyncio.run(synth())
        except Exception as e:  # undocumented endpoint — treat any failure as degrade
            raise SynthesisError(f"edge-tts failed: {e}") from e
        if not data:
            raise SynthesisError("edge-tts returned no audio")
        return decode_audio_bytes(data, ".mp3")


class OpenAIEngine:
    name = "openai"

    def __init__(self, language: str, voice: str):
        from openai import OpenAI
        key = config.load_env().get("OPENAI_API_KEY")
        if not key:
            raise SynthesisError(f"OPENAI_API_KEY not in {config.ENV_PATH}")
        self.voice = voice
        self.client = OpenAI(api_key=key)

    def render(self, paragraph: str) -> tuple[np.ndarray, int]:
        resp = self.client.audio.speech.create(
            model=config.OPENAI_TTS_MODEL, voice=self.voice, input=paragraph,
            response_format="wav")
        samples, sr = sf.read(io.BytesIO(resp.content), dtype="float32")
        return _mono(samples), sr


ENGINES = {"kokoro": KokoroEngine, "edge_tts": EdgeTTSEngine, "openai": OpenAIEngine}


def _render_story(engine, paragraphs: list[str],
                  should_abort=None) -> tuple[np.ndarray, int, list[float]]:
    parts, durations, sr = [], [], None
    for i, p in enumerate(paragraphs):
        if should_abort and should_abort():
            raise AbortRender(
                f"story skipped/read or voice changed at paragraph {i}")
        samples, this_sr = engine.render(p)
        if sr is None:
            sr = this_sr
        elif this_sr != sr:
            raise SynthesisError(f"sample-rate changed mid-story: {sr} -> {this_sr}")
        parts.append(samples)
        durations.append(len(samples) / sr)
        print(f"  [synth] para {i + 1}/{len(paragraphs)}: {durations[-1]:.1f}s")
    return np.concatenate(parts), sr, durations


def synthesize_story(paragraphs: list[str], language: str, out_m4a: pathlib.Path,
                     voice_override: str | None = None, should_abort=None):
    """Render all paragraphs with the language's primary engine; on failure,
    restart the story on OpenAI TTS (per-story fallback). Writes out_m4a and
    returns (engine_name, voice, sample_rate, durations_s).

    voice_override (AMENDMENT_04 D) swaps the voice within the language's
    configured engine; should_abort() is polled between paragraphs."""
    config.INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    engine_name, voice = config.TTS_BY_LANGUAGE.get(language, config.FALLBACK_TTS)
    if voice_override:
        voice = voice_override
    attempts = [(engine_name, voice)]
    if engine_name != config.FALLBACK_TTS[0]:
        attempts.append(config.FALLBACK_TTS)

    last_err = None
    for name, v in attempts:
        # catch everything, not just SynthesisError: the degrade rule (DESIGN
        # §9.6) must fire on Kokoro/edge-tts internal errors too, or a raw
        # RuntimeError bypasses the OpenAI fallback entirely. AbortRender is
        # the one deliberate exception — a skip must not start a paid render.
        try:
            engine = ENGINES[name](language, v)
            audio, sr, durations = _render_story(engine, paragraphs, should_abort)
            _write_m4a(audio, sr, out_m4a)
            return name, v, sr, durations
        except AbortRender:
            raise
        except Exception as e:
            print(f"  [synth] {name} failed ({e}); "
                  f"{'falling back to OpenAI' if (name, v) != config.FALLBACK_TTS else 'no fallback left'}")
            last_err = e
    raise SynthesisError(f"all engines failed for language={language}: {last_err}")


def _write_m4a(audio: np.ndarray, sr: int, out_m4a: pathlib.Path):
    out_m4a.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=config.INTERIM_DIR) as td:
        wav = pathlib.Path(td) / "story.wav"
        sf.write(wav, audio, sr)
        proc = subprocess.run(
            ["afconvert", "-f", "m4af", "-d", "aac", "-b", "64000",
             str(wav), str(out_m4a)],
            capture_output=True, text=True)
        if proc.returncode != 0:
            raise SynthesisError(f"afconvert encode failed: {proc.stderr.strip()}")
    # wav interim deleted with the tempdir (DESIGN §2)
