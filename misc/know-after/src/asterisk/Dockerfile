# Asterisk 20 (Ubuntu 24.04 package) with PJSIP + AudioSocket.
# Media never leaves this box: the softphone talks SIP/RTP to this container,
# and the container streams raw 8 kHz PCM to the SocEngLLM app container
# (AUDIOSOCKET_SERVER, default app:9092) over AudioSocket (TCP).
FROM ubuntu:24.04

RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      asterisk asterisk-modules asterisk-core-sounds-en-gsm ca-certificates curl \
 && rm -rf /var/lib/apt/lists/*

# Overlay our config on top of the package's sample configs (the samples keep
# modules that want a config file quiet; ours win where they overlap).
COPY conf/ /etc/asterisk/
RUN mv /etc/asterisk/pjsip.conf /etc/asterisk/pjsip.conf.in \
 && mv /etc/asterisk/extensions.conf /etc/asterisk/extensions.conf.in
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 5060/udp 5060/tcp 5080/udp 10000-10010/udp

# entrypoint renders pjsip.conf from EXTERNAL_ADDRESS, then runs asterisk in
# the foreground (-f) with a verbose console; logs go to `docker logs`.
ENTRYPOINT ["/entrypoint.sh"]
