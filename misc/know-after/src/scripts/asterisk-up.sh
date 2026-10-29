#!/bin/sh
# Start (or restart) the whole stack (app, web viewer, Asterisk) with docker compose, advertising
# this machine's Tailscale IP to softphones when Tailscale is up.
#   scripts/asterisk-up.sh            auto-detect (Tailscale IP, else 127.0.0.1)
#   scripts/asterisk-up.sh 10.0.0.5   explicit address
# Dev variant with the app on the host instead of in a container:
#   AUDIOSOCKET_SERVER=host.docker.internal:9092 docker compose up -d --build asterisk
cd "$(dirname "$0")/.."
ADDR="$1"
if [ -z "$ADDR" ]; then
  for ts in tailscale /Applications/Tailscale.app/Contents/MacOS/Tailscale; do
    ADDR=$("$ts" ip -4 2>/dev/null | head -1) && [ -n "$ADDR" ] && break
  done
fi
ADDR="${ADDR:-127.0.0.1}"
PUB="${TRUNK_EXTERNAL_ADDRESS:-$(curl -s --max-time 5 https://api.ipify.org || true)}"
echo "Asterisk will advertise ${ADDR} to softphones and ${PUB:-<auto>} to the SIP trunk"
mkdir -p logs/asterisk calls
EXTERNAL_ADDRESS="$ADDR" TRUNK_EXTERNAL_ADDRESS="$PUB" docker compose up -d --build --force-recreate
