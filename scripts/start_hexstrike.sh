#!/bin/bash
# Starts HexStrike inside WSL with pipx's bin dir on PATH (arjun/paramspider live there).
# Assumes hexstrike-ai is a sibling of this repo — derives its path from this
# script's own location instead of hardcoding a username.
export PATH="$PATH:/root/.local/bin"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec /root/hexstrike-env/bin/python "$SCRIPT_DIR/../../hexstrike-ai/hexstrike_server.py"
