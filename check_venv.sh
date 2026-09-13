#!/bin/bash
# Sanity check that HexStrike's WSL venv (/root/hexstrike-env) has its deps installed.
/root/hexstrike-env/bin/python -c "import flask; print('flask ok')"
