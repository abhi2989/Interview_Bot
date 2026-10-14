#!/bin/bash
# Virtual audio plumbing:
#   TTS wav --paplay--> bot_mic sink -> bot_mic_src (Chrome's microphone -> candidate hears bot)
#   Chrome speaker (candidate voice) -> meeting_out sink -> meeting_out.monitor (we record this)
set -e
Xvfb :99 -screen 0 1280x720x24 &
export DISPLAY=:99
pulseaudio -D --exit-idle-time=-1 --disallow-exit || true
sleep 1
pactl load-module module-null-sink sink_name=meeting_out
pactl load-module module-null-sink sink_name=bot_mic
pactl load-module module-remap-source master=bot_mic.monitor source_name=bot_mic_src
pactl set-default-sink meeting_out
pactl set-default-source bot_mic_src
exec python -m src.main "$@"
