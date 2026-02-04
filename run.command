#!/bin/bash
# Double-click to run Bezel Remover. First time: creates venv and installs deps.
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
    python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
else
    source .venv/bin/activate
fi
python app.py
