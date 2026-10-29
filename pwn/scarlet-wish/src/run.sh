#!/bin/bash
# Serve Scarlet Wish (acctd) on $PORT, one process per connection, the way
# inetd does it. timeout caps each session.
#
#   run.sh           check the flag, then serve
#   run.sh --check   check the flag only; the image build runs this
#
# Environment, with defaults set in the Dockerfile:
#   ACCTD            the server binary
#   ACCT_DIR         the account store; the flag lives at $ACCT_DIR/admin/flag,
#                    and acctd inherits this variable to find the store itself
#   PORT             where to listen for players
#   SESSION_SECONDS  the longest one connection may run; a backstop, since
#                    acctd has no idle timer of its own
#   MAX_CONNS        concurrent connections, via socat's max-children; empty
#                    for no cap
#   TELEMETRY_AUTH_FILE  user:password for the stderr log viewer's Basic Auth
#   TELEMETRY_HOST   where the log viewer listens (default 0.0.0.0)
#   TELEMETRY_PORT   the log viewer's port (default 9101)
set -euo pipefail

app=$(dirname "$(readlink -f "$0")")
bin=${ACCTD:-/usr/local/bin/acctd}
store=${ACCT_DIR:-/srv/acct}
flag_file=${store}/admin/flag
port=${PORT:-5000}
auth_file=${TELEMETRY_AUTH_FILE:?TELEMETRY_AUTH_FILE is not set}

fail() {
    echo "run.sh: $*" >&2
    exit 1
}

[ -x "${bin}" ] || fail "${bin} is missing or not executable"
[ -r "${flag_file}" ] || fail "${flag_file} is missing or unreadable"
[ -s "${flag_file}" ] || fail "${flag_file} is empty"
# Current beaverCDS trims a trailing newline from the scoreboard flag, and
# a command substitution drops it below, so only multi-line content is a
# problem.
[ "$(grep -c '' "${flag_file}")" -eq 1 ] || fail "${flag_file} must be exactly one line"
flag=$(cat "${flag_file}")
case "${flag}" in
    pdx\{*\}) ;;
    *) fail "${flag_file} does not look like pdx{...}" ;;
esac
case "${flag}" in
    *placeholder*|*dev_flag*) fail "${flag_file} is a development placeholder, not a real flag" ;;
esac

# The stderr log viewer is only as private as its Basic Auth, so refuse to
# serve without a well-formed credential, the way the image build checks it.
[ -r "${auth_file}" ] || fail "${auth_file} is missing or unreadable"
[ "$(grep -c '' "${auth_file}")" -eq 1 ] || fail "${auth_file} must be exactly one line"
auth=$(cat "${auth_file}")
case "${auth}" in
    ?*:?*) ;;
    *) fail "${auth_file} must be user:password, both non-empty" ;;
esac

if [ "${1:-}" = --check ]; then
    echo "run.sh: flag and telemetry auth ok"
    exit 0
fi

opts=reuseaddr,fork,keepalive
[ -n "${MAX_CONNS:-}" ] && opts=${opts},max-children=${MAX_CONNS}

# stderr-web.py is the parent: it runs socat, collects every acctd stderr line
# into a buffer, and serves it behind Basic Auth so authors can watch what
# players try without reach to the container's own logs. acctd tags each line
# with its pid and the client address, which --columns turns into sortable,
# filterable columns. socat exports the client address as SOCAT_PEERADDR to each
# connection; --peer-env tells acctd to read it from there, so the source need
# not name the front end. When socat exits, the wrapper exits with its status,
# so the pod restarts just as a bare socat would.
echo "run.sh: serving acctd on ${port}, log viewer on ${TELEMETRY_PORT:-9101}"
exec python3 "${app}/stderr-web.py" \
    --title "Scarlet Wish requests" --columns pid,ip --auth "${auth}" \
    --host "${TELEMETRY_HOST:-0.0.0.0}" --port "${TELEMETRY_PORT:-9101}" \
    -- socat "TCP-LISTEN:${port},${opts}" \
        "EXEC:timeout -k 5 ${SESSION_SECONDS:-600} ${bin} --peer-env SOCAT_PEERADDR"
