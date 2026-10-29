#!/bin/sh
# Render pjsip.conf from environment, then start Asterisk.
set -e
ADDR="${EXTERNAL_ADDRESS:-127.0.0.1}"
PUB="${TRUNK_EXTERNAL_ADDRESS:-}"
if [ -z "$PUB" ]; then
  PUB=$(curl -s --max-time 5 https://api.ipify.org || true)
fi
PUB="${PUB:-$ADDR}"
mkdir -p /var/log/asterisk/socengllm
sed -e "s/__EXTERNAL_ADDRESS__/${ADDR}/g" \
    -e "s/__TRUNK_EXTERNAL_ADDRESS__/${PUB}/g" \
    -e "s/__TRUNK_HOST__/${TRUNK_HOST:-sanjose2.voip.ms}/g" \
    -e "s/__TRUNK_USER__/${TRUNK_USER:-trunk-user-unset}/g" \
    -e "s#__TRUNK_PASSWORD__#${TRUNK_PASSWORD:-trunk-password-unset}#g" \
    -e "s/__TRUNK_DID__/${TRUNK_DID:-}/g" \
    /etc/asterisk/pjsip.conf.in > /etc/asterisk/pjsip.conf
sed -e "s/__AUDIOSOCKET_SERVER__/${AUDIOSOCKET_SERVER:-app:9092}/g" \
    /etc/asterisk/extensions.conf.in > /etc/asterisk/extensions.conf
echo "pjsip softphone address: ${ADDR}   trunk address: ${PUB}   trunk: ${TRUNK_USER:-unset}@${TRUNK_HOST:-sanjose2.voip.ms}   audiosocket: ${AUDIOSOCKET_SERVER:-app:9092}"
exec asterisk -f -g
