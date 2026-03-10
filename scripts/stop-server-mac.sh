#!/usr/bin/env bash
set -euo pipefail

CONTAINER_NAME="pm-mvp"

if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
  echo "Stopping and removing container: $CONTAINER_NAME"
  docker rm -f "$CONTAINER_NAME" >/dev/null
  echo "Container removed."
else
  echo "Container not found: $CONTAINER_NAME"
fi
