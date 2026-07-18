#!/usr/bin/env python3
"""Probe 5: phone playback reality — serve the test page + audio for iOS Safari over
Tailscale. Uses FastAPI StaticFiles (same mechanism Phase 4 will use), which supports
HTTP Range requests.

Binding policy per CLAUDE.md: never listen beyond Tailscale. Default bind is 127.0.0.1
(local verification). Once Tailscale is installed, pass the Mac's 100.x address:
    .venv/bin/python probe5_phone_server.py 100.x.y.z
Throwaway code — no authority after Phase 1.
"""
import pathlib
import sys

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

ROOT = pathlib.Path(__file__).resolve().parent
DATA = ROOT.parents[0] / "data" / "interim"

app = FastAPI()
app.mount("/audio", StaticFiles(directory=DATA), name="audio")
app.mount("/", StaticFiles(directory=ROOT / "probe5_static", html=True), name="page")

if __name__ == "__main__":
    host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    uvicorn.run(app, host=host, port=8765, log_level="info")
