#!/bin/sh

# mitigate race condition with asterisk startup
sleep 5

exec baresip -f /etc/baresip
