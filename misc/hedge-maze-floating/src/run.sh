#!/bin/bash
# Serve one Hedge Maze tier on $PORT, one game process per connection, and its
# telemetry watcher on $TELEMETRY_HOST:$TELEMETRY_PORT.
#
#   run.sh           check the flag, then serve
#   run.sh --check   check the flag only; the image build runs this
#
# Environment, with defaults set in the Dockerfile:
#   TIER_SCRIPT          the tier, e.g. challenge-key.py, beside this script
#   HEDGEMAZE_FLAG_FILE  the flag file hedgemaze.load_flag() reads
#   HEDGEMAZE_TELEMETRY  where each game records itself
#   TELEMETRY_AUTH_FILE  the watcher's user:password for Basic Auth
#   PORT                 where to listen for players
#   TELEMETRY_HOST       where the watcher listens. It draws every maze's
#   TELEMETRY_PORT       solution, so its Basic Auth must stay on.
#   MAX_GAMES            concurrent games, via socat's max-children; empty for
#                        no cap. Keep it under the pod's memory limit / 50MB.
#   HEDGEMAZE_IDLE_SECONDS  how long the game lets a player sit at the prompt
#                        before dropping them; read by hedgemaze.py itself
#   SESSION_SECONDS      the longest one game may run, idle or not: a backstop
#                        well past any real solve
set -euo pipefail

app=$(dirname "$(readlink -f "$0")")
script=${app}/${TIER_SCRIPT:?TIER_SCRIPT is not set}
flag_file=${HEDGEMAZE_FLAG_FILE:?HEDGEMAZE_FLAG_FILE is not set}
auth_file=${TELEMETRY_AUTH_FILE:?TELEMETRY_AUTH_FILE is not set}

fail() {
    echo "run.sh: $*" >&2
    exit 1
}

# hedgemaze.load_flag() refuses a bad flag file too, but only when a player
# wins, while the listener stays up and looks healthy. Check before serving.
[ -r "${script}" ] || fail "${script} is missing"
[ -r "${flag_file}" ] || fail "${flag_file} is missing or unreadable"
[ -s "${flag_file}" ] || fail "${flag_file} is empty"
# Current beaverCDS trims a trailing newline from the scoreboard flag and the
# game strips it too, so only genuinely multi-line content is a problem.
[ "$(grep -c '' "${flag_file}")" -eq 1 ] || fail "${flag_file} must be exactly one line"
flag=$(cat "${flag_file}")
case "${flag}" in
    pdx\{*\}) ;;
    *) fail "${flag_file} does not look like pdx{...}" ;;
esac
# Every tier script carries a placeholder flag. Serving it would hand every
# winner a useless flag for the whole event.
if grep -qF -- "${flag}" "${script}"; then
    fail "${flag_file} is the placeholder flag built into ${TIER_SCRIPT}"
fi

[ -r "${auth_file}" ] || fail "${auth_file} is missing or unreadable"
[ "$(grep -c '' "${auth_file}")" -eq 1 ] || fail "${auth_file} must be exactly one line"
auth=$(cat "${auth_file}")
case "${auth}" in
    ?*:?*) ;;
    *) fail "${auth_file} must be user:password, both non-empty" ;;
esac

if [ "${1:-}" = --check ]; then
    echo "run.sh: flag and telemetry auth ok for ${TIER_SCRIPT}"
    exit 0
fi

telemetry=${HEDGEMAZE_TELEMETRY:?HEDGEMAZE_TELEMETRY is not set}
mkdir -p "${telemetry}"
# Not fatal, since the games still play and telemetry disables itself, but
# never what anyone meant.
[ -w "${telemetry}" ] || echo "run.sh: ${telemetry} is not writable; no runs will be recorded" >&2

children=()
stopping=0
shutdown() {
    trap - TERM INT
    stopping=1
    kill "${children[@]}" 2>/dev/null || true
}
trap shutdown TERM INT

opts=reuseaddr,fork,keepalive
[ -n "${MAX_GAMES:-}" ] && opts=${opts},max-children=${MAX_GAMES}

# nofork makes socat exec the game straight onto the accepted socket, as inetd
# does, rather than relaying through a socketpair. That is also what lets
# telemetry record each player's address. Never add --test, --seed, or
# --verify: the first two give the maze away, and --verify removes the
# per-move delay that is the anti-automation measure.
socat "TCP-LISTEN:${PORT},${opts}" \
    "EXEC:timeout -k 5 ${SESSION_SECONDS:-28800} python3 -u ${script},nofork" &
children+=("$!")
echo "run.sh: serving ${TIER_SCRIPT} on ${PORT}"

python3 "${app}/telemetry-web.py" --dir "${telemetry}" --auth "${auth}" \
    --host "${TELEMETRY_HOST:-0.0.0.0}" --port "${TELEMETRY_PORT:-9101}" &
children+=("$!")

# Either one exiting means the tier is dark or the watcher is gone: fail the
# pod so Kubernetes restarts it. wait -n returns the dead child's status, so
# `|| true` keeps set -e from skipping the cleanup below.
wait -n || true
if [ "${stopping}" -eq 1 ]; then
    wait 2>/dev/null || true
    exit 0
fi
echo "run.sh: a service exited; stopping the rest" >&2
shutdown
wait 2>/dev/null || true
exit 1
