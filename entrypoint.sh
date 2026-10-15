#!/bin/bash
set -e
Xvfb :99 -screen 0 1280x800x24 &
export DISPLAY=:99
rm -f /app/data/profile/Singleton* 2>/dev/null || true     # stale lock from a previous container

if [ "$1" = "--login" ]; then
  # ONE-TIME: sign in to Google inside this same Linux browser, through your own browser at http://localhost:6080/vnc.html
  openbox &
  x11vnc -display :99 -forever -shared -nopw -rfbport 5900 -quiet &
  websockify --web=/usr/share/novnc 6080 localhost:5900 >/dev/null 2>&1 &
  CHROME=$(python - <<'PY'
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    print(p.chromium.executable_path)
PY
)
  echo
  echo "=== Open http://localhost:6080/vnc.html in your browser and click Connect ==="
  echo "=== Sign in to Google. When done, CLOSE the Chromium window (or press Ctrl+C here). ==="
  "$CHROME" --no-sandbox --disable-dev-shm-usage --user-data-dir=/app/data/profile \
            --no-first-run --window-size=1280,780 --window-position=0,0 https://accounts.google.com &
  CPID=$!
  trap 'kill -TERM $CPID 2>/dev/null; wait $CPID 2>/dev/null; exit 0' INT TERM
  wait $CPID || true
  echo "Login saved in data/profile."
  exit 0
fi

# Virtual audio plumbing:
#   TTS wav --paplay--> bot_mic sink -> bot_mic_src (Chrome's microphone -> candidate hears bot)
#   Chrome speaker (candidate voice) -> meeting_out sink -> meeting_out.monitor (we record this)
pulseaudio -D --exit-idle-time=-1 --disallow-exit || true
sleep 1
pactl load-module module-null-sink sink_name=meeting_out
pactl load-module module-null-sink sink_name=bot_mic
pactl load-module module-remap-source master=bot_mic.monitor source_name=bot_mic_src
pactl set-default-sink meeting_out
pactl set-default-source bot_mic_src
exec python -m src.main "$@"
