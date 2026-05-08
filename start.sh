#!/bin/bash

source venv/bin/activate

WHISPER_TRANSCRIPTION_URL=http://localhost:8090/v1/audio/transcriptions

python3 main.py
