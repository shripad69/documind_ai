#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is not installed or is not available in PATH." >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "Docker Compose is not available. Install Docker Compose v2 and try again." >&2
  exit 1
fi

echo "Building and starting the Document Chatbot workspace platform..."
docker compose --progress plain up --build -d --force-recreate --remove-orphans

echo
docker compose ps
echo
echo "Frontend: http://localhost:8080"
echo "Backend:  http://localhost:8000"
echo "API docs: http://localhost:8000/docs"
echo
echo "Following live logs (Ctrl+C stops log viewing; services keep running)..."
exec docker compose logs --follow --tail=100 --timestamps backend worker db redis frontend
