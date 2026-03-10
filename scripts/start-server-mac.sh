#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
IMAGE_NAME="pm-mvp:dev"
CONTAINER_NAME="pm-mvp"
VOLUME_NAME="pm-mvp-data"

cd "$PROJECT_ROOT"

echo "Building Docker image: $IMAGE_NAME"
docker build -t "$IMAGE_NAME" .

echo "Removing existing container (if any): $CONTAINER_NAME"
docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true

RUN_ARGS=(
  -d
  --name "$CONTAINER_NAME"
  -p 8000:8000
  -v "$VOLUME_NAME:/app/backend/data"
)

if [[ -f "$PROJECT_ROOT/.env" ]]; then
  RUN_ARGS+=(--env-file "$PROJECT_ROOT/.env")
fi

echo "Starting container: $CONTAINER_NAME"
docker run "${RUN_ARGS[@]}" "$IMAGE_NAME" >/dev/null

echo "App is starting at http://127.0.0.1:8000"
echo "Health endpoint: http://127.0.0.1:8000/api/health"
