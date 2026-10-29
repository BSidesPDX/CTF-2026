#!/bin/sh

export THE_FLAG=$(cat flag.txt)
export JWT_SECRET_KEY=$(python3 -c "import secrets;print(secrets.token_hex(32), end='')")

uv run --locked --no-dev fastapi run
