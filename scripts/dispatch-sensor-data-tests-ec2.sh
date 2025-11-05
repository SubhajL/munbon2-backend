#!/usr/bin/env bash
set -euo pipefail

# Simple dispatcher to run sensor-data tests on EC2 over SSH
# Usage:
#   scripts/dispatch-sensor-data-tests-ec2.sh \
#     --host 43.208.201.191 --key ~/dev/th-lab01.pem --user ubuntu \
#     --repo /home/ubuntu/munbon2-backend

HOST=""
KEY=""
USER="ubuntu"
REPO_DIR="/home/ubuntu/munbon2-backend"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) HOST="$2"; shift 2 ;;
    --key) KEY="$2"; shift 2 ;;
    --user) USER="$2"; shift 2 ;;
    --repo) REPO_DIR="$2"; shift 2 ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

if [[ -z "$HOST" || -z "$KEY" ]]; then
  echo "Missing --host or --key"
  exit 1
fi

ssh -o StrictHostKeyChecking=no -i "$KEY" ${USER}@${HOST} "bash -lc '
  set -e
  if [ ! -d \"$REPO_DIR\" ]; then
    echo \"Repo dir not found: $REPO_DIR\"
    exit 1
  fi
  cd \"$REPO_DIR\"
  git fetch --all --prune
  git reset --hard origin/$(git rev-parse --abbrev-ref HEAD)
  cd services/sensor-data
  if [ -f package-lock.json ]; then npm ci; else npm i; fi
  npm test -- --runInBand
'"

echo "✅ Remote tests completed on ${HOST}"

