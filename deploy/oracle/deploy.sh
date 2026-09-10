#!/usr/bin/env bash
set -Eeuo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required." >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker daemon is not running." >&2
  exit 1
fi

docker compose build --pull
docker compose up -d --remove-orphans
docker compose ps

echo
echo "PhysicsLab is available at http://$(hostname -I | awk '{print $1}')/"
echo "Health check: http://$(hostname -I | awk '{print $1}')/health"
