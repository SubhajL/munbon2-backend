#!/bin/bash
cd "$(dirname "$0")"

# Load environment variables from .env, but ONLY as a fallback: an environment
# variable already injected by PM2 (PORT, POSTGRES_URL, ...) is AUTHORITATIVE and
# must never be clobbered by a stale .env value. Otherwise PM2 could migrate one
# DB while the runtime serves another. Bash indirect expansion (${!_key+x})
# exports a .env KEY=VALUE only when that key is currently UNSET in the environment.
if [ -f .env ]; then
  while IFS= read -r _line || [ -n "$_line" ]; do
    case "$_line" in ''|\#*) continue;; esac
    _key=${_line%%=*}
    if [ -z "${!_key+x}" ]; then export "$_line"; fi
  done < .env
fi

export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"

# Migrate-before-start: apply every tracked migration pair, then exec uvicorn
# ONLY on success. A checksum drift or an unreachable DB aborts startup here so
# PM2 never boots a process whose prediction schema is missing or drifted.
./venv/bin/python migrations/migrate.py apply-all || exit 1

# Flow-monitoring stays on 3011 (PM2 flow PORT=3011).
exec ./venv/bin/uvicorn src.main:app --host 0.0.0.0 --port 3011
