#!/usr/bin/env bash
# Regenerates tests/fixtures/speech_sample.wav, a short REAL speech clip used by
# the transcription tests. It needs espeak-ng (apt install espeak-ng / brew
# install espeak-ng) and ffmpeg. You can also record yourself saying the text
# below and save it as 16 kHz mono WAV with the same name.
set -euo pipefail
cd "$(dirname "$0")"
TEXT="Speech recognition converts spoken language into text. The acoustic model and the language model work together."
espeak-ng -v en-us -s 140 -w /tmp/lm_fixture_raw.wav "$TEXT"
ffmpeg -y -loglevel error -i /tmp/lm_fixture_raw.wav -ac 1 -ar 16000 speech_sample.wav
rm -f /tmp/lm_fixture_raw.wav
echo "wrote $(pwd)/speech_sample.wav"
