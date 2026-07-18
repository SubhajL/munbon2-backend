#!/bin/bash
cd "$(dirname "$0")"

# Load environment variables from .env, but ONLY as a fallback: an environment
# variable already injected by PM2 (PORT, POSTGRES_URL, ...) is AUTHORITATIVE and
# must never be clobbered by a stale .env value. Otherwise PM2 could set PORT=3021
# while .env says 3012 (defeating the port migration), or migrate one DB while the
# runtime serves another. Bash indirect expansion (${!_key+x}) exports a .env
# KEY=VALUE only when that key is currently UNSET in the environment.
if [ -f .env ]; then
  while IFS= read -r _line || [ -n "$_line" ]; do
    case "$_line" in ''|\#*) continue;; esac
    _key=${_line%%=*}
    if [ -z "${!_key+x}" ]; then export "$_line"; fi
  done < .env
fi

export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"

# Migrate-before-start: apply every tracked migration pair, then exec uvicorn
# ONLY on success. A checksum drift or an unreachable DB makes the runner exit
# non-zero and aborts startup here, so PM2 never boots a process that would
# report /ready while its schema is missing or drifted.
./venv/bin/python migrations/migrate.py apply-all || exit 1

# Canonical scheduler port is 3021; honor an explicit $PORT (PM2 sets 3021).
exec ./venv/bin/uvicorn src.main:app --host 0.0.0.0 --port "${PORT:-3021}"
