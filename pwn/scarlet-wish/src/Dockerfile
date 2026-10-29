# Scarlet Wish (acctd): the Westview Library account server, built from the
# Rust front end and the C store in pwn/scarlet-wish/ and served over socat,
# one process per connection.
#
# The sources (Cargo.*, build.rs, src/, csrc/) are symlinks into
# pwn/scarlet-wish/ in the repository; beaverCDS dereferences them when it
# packs the build context. A plain `docker build` does not, so build by hand
# through a dereferencing tar:
#   tar -ch -C infra/pwn/scarlet-wish . | docker build -t scarlet-wish -
# (see infra/README.md).
ARG RUST_VERSION=1.83

FROM rust:${RUST_VERSION}-slim AS build
# build.rs compiles csrc/acct.c with cc and ar, which the rust image lacks.
RUN apt-get update \
 && apt-get install -y --no-install-recommends gcc \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /src
COPY Cargo.toml Cargo.lock build.rs ./
COPY src ./src
COPY csrc ./csrc
# No external crates, so cargo never reaches the network; --locked proves it.
RUN cargo build --release --locked

FROM debian:bookworm-slim
# socat is the accept-and-exec front end: one acctd per connection, the way
# inetd does it. timeout, from coreutils, caps a session. python3 runs the
# stderr log viewer (stdlib only, no pip).
RUN apt-get update \
 && apt-get install -y --no-install-recommends socat python3 \
 && rm -rf /var/lib/apt/lists/*

COPY --from=build /src/target/release/acctd /usr/local/bin/acctd
COPY run.sh /usr/local/bin/run.sh
COPY stderr-web.py /usr/local/bin/stderr-web.py
# The log viewer's user:password, git-ignored in the challenge directory like
# the flag; the image build checks it below.
COPY telemetry-auth /usr/local/bin/telemetry-auth

# The account store. admin owns the flag; guest's password file is what lets
# guest/guest log in. tree/ is the sample store shipped to players and carries
# a placeholder flag; COPY flag then installs the real one over it. The real
# flag is git-ignored in the challenge directory, where beaverCDS reads the
# same file for the scoreboard, so it is inside the image.
COPY tree/ /srv/acct/
COPY flag /srv/acct/admin/flag

ENV ACCTD=/usr/local/bin/acctd \
    ACCT_DIR=/srv/acct \
    PORT=5000 \
    SESSION_SECONDS=600 \
    MAX_CONNS=64 \
    TELEMETRY_AUTH_FILE=/usr/local/bin/telemetry-auth \
    TELEMETRY_HOST=0.0.0.0 \
    TELEMETRY_PORT=9101 \
    PYTHONUNBUFFERED=1

# The service runs as ctf, which does not own the store and cannot write it:
# that is what keeps WRITEFILE a dead end, so the decoy stays a decoy and no
# connection can corrupt the flag for the others. Check the flag while still
# root, then lock the store read-only and drop privileges.
RUN chmod 0755 /usr/local/bin/run.sh /usr/local/bin/stderr-web.py \
 && chmod 0644 /usr/local/bin/telemetry-auth \
 && /usr/local/bin/run.sh --check \
 && useradd --system --no-create-home --shell /usr/sbin/nologin ctf \
 && chown -R root:root /srv/acct \
 && find /srv/acct -type d -exec chmod 0555 {} + \
 && find /srv/acct -type f -exec chmod 0444 {} +

USER ctf
EXPOSE 5000 9101
ENTRYPOINT ["/usr/local/bin/run.sh"]
