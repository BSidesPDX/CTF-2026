#!/usr/bin/env bash

host="127.0.0.1"
port=3030

jwt=$(curl -vs "http://${host}:${port}/" 2>&1 | grep -E 'set-cookie: gamestate=[0-9a-zA-Z_-]+[.][0-9a-zA-Z_-]+[.][0-9a-zA-Z_-]+' | sed -E 's/^.*gamestate=([0-9a-zA-Z_-]+[.][0-9a-zA-Z_-]+[.][0-9a-zA-Z_-]+).*$/\1/')
echo "0: ${jwt}"

jwt=$(curl -vs -X POST "http://${host}:${port}/X/_" -H "Host: cell9.localhost" -H "cookie: gamestate=${jwt};" 2>&1 | grep -E 'set-cookie: gamestate=[0-9a-zA-Z_-]+[.][0-9a-zA-Z_-]+[.][0-9a-zA-Z_-]+' | sed -E 's/^.*gamestate=([0-9a-zA-Z_-]+[.][0-9a-zA-Z_-]+[.][0-9a-zA-Z_-]+).*$/\1/')
echo "1: ${jwt}"

jwt=$(curl -vs -X POST "http://${host}:${port}/X/_" -H "Host: cell10.localhost" -H "cookie: gamestate=${jwt};" 2>&1 | grep -E 'set-cookie: gamestate=[0-9a-zA-Z_-]+[.][0-9a-zA-Z_-]+[.][0-9a-zA-Z_-]+' | sed -E 's/^.*gamestate=([0-9a-zA-Z_-]+[.][0-9a-zA-Z_-]+[.][0-9a-zA-Z_-]+).*$/\1/')
echo "2: ${jwt}"

echo "$(curl -s -X POST "http://${host}:${port}/X/_" -H "Host: cell11.localhost" -H "cookie: gamestate=${jwt};" 2>&1)"
