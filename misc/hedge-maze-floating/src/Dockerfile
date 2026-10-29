# Hedge Maze, one tier per image, for beaverCDS: the game on 31337 and its
# telemetry watcher on 9101.
#
# Every misc/hedge-maze*/ challenge directory links this file and passes its tier in
# as build args from its challenge.yaml. The challenge sources are symlinks into
# misc/hedge-maze/ in the repository; beaverCDS dereferences them when it packs
# the build context. A plain `docker build` does not, so test with
#   tar -ch -C infra/misc/hedge-maze . | docker build --build-arg ... -
# (see infra/README.md).
#
# PYTHON_VERSION defaults to 3.13 on purpose: mazelib declares
# requires_python <3.14, so a newer base fails at pip time with nothing more
# helpful than "no matching distribution". The check after FROM says so plainly.
ARG PYTHON_VERSION=3.13
FROM python:${PYTHON_VERSION}-slim

ARG TIER_SCRIPT

RUN python3 -c 'import sys; v = sys.version_info[:2]; sys.exit("mazelib needs Python < 3.14 but this is %d.%d: build with PYTHON_VERSION=3.13" % v if v >= (3, 14) else 0)'
RUN test -n "${TIER_SCRIPT}" || { echo "TIER_SCRIPT build arg is not set" >&2; exit 1; }

# socat is the accept-and-exec front end: one game process per connection, the
# way inetd does it. timeout, from coreutils, caps a session.
RUN apt-get update \
 && apt-get install -y --no-install-recommends socat \
 && rm -rf /var/lib/apt/lists/*

# mazelib, adventurelib, and numpy all ship wheels, so no compiler is installed.
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r /app/requirements.txt

# Only what this tier needs: not the solvers or the other tiers.
COPY hedgemaze.py ${TIER_SCRIPT} run.sh /app/
COPY telemetry-web.py telemetry-web.html /app/

# The real flag, from the challenge directory, where it is git-ignored and
# beaverCDS reads the same file for the scoreboard. run.sh --check refuses a
# flag that is missing, malformed, or the placeholder built into the script.
COPY flag /app/flag

# The telemetry watcher's user:password, also git-ignored in the challenge
# directory. The watcher draws every maze's solution; beaverCDS exposes it
# over HTTPS, and its Basic Auth is all that keeps players out.
COPY telemetry-auth /app/telemetry-auth

ENV TIER_SCRIPT=${TIER_SCRIPT} \
    HEDGEMAZE_FLAG_FILE=/app/flag \
    HEDGEMAZE_TELEMETRY=/srv/telemetry \
    TELEMETRY_AUTH_FILE=/app/telemetry-auth \
    PORT=31337 \
    TELEMETRY_HOST=0.0.0.0 \
    TELEMETRY_PORT=9101 \
    MAX_GAMES=32 \
    HEDGEMAZE_IDLE_SECONDS=300 \
    SESSION_SECONDS=28800 \
    PYTHONUNBUFFERED=1

RUN chmod 0755 /app/run.sh \
 && chmod 0644 /app/flag /app/telemetry-auth \
 && /app/run.sh --check \
 && useradd --system --no-create-home --shell /usr/sbin/nologin ctf \
 && mkdir -p /srv/telemetry \
 && chown ctf:ctf /srv/telemetry

# The game user owns nothing under /app, only the telemetry directory.
USER ctf
WORKDIR /app
EXPOSE 31337 9101
ENTRYPOINT ["/app/run.sh"]
