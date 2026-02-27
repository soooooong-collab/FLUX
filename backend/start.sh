#!/bin/bash
export PYTHONPATH="/Users/song/Documents/FLUX v0.1/backend"
export PATH="/Users/song/Documents/FLUX v0.1/backend/venv/bin:$PATH"
cd "/Users/song/Documents/FLUX v0.1/backend"
exec "/Users/song/Documents/FLUX v0.1/backend/venv/bin/python3" -m uvicorn main:app --reload --host 0.0.0.0 --port "${PORT:-8000}"
