#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT_DIR/.env}"
backup="${1:-}"
confirmation="${2:-}"

if [[ ! -f "$backup" ]]; then
  echo "Usage: $0 /absolute/path/to/backup.dump --confirm" >&2
  exit 1
fi
if [[ "$confirmation" != "--confirm" ]]; then
  echo "Restore requires --confirm" >&2
  exit 1
fi

backup="$(cd "$(dirname "$backup")" && pwd)/$(basename "$backup")"
set -a
source "$ENV_FILE"
set +a

restart_services() {
  docker compose --project-directory "$ROOT_DIR" --env-file "$ENV_FILE" up -d api worker
}
trap restart_services EXIT

docker compose --project-directory "$ROOT_DIR" --env-file "$ENV_FILE" stop api worker
docker compose --project-directory "$ROOT_DIR" --env-file "$ENV_FILE" exec -T db \
  dropdb --force --if-exists --username "$POSTGRES_USER" "$POSTGRES_DB"
docker compose --project-directory "$ROOT_DIR" --env-file "$ENV_FILE" exec -T db \
  createdb --username "$POSTGRES_USER" "$POSTGRES_DB"
docker compose --project-directory "$ROOT_DIR" --env-file "$ENV_FILE" exec -T db \
  pg_restore --exit-on-error --no-owner --no-privileges \
  --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" < "$backup"

restart_services
trap - EXIT
docker compose --project-directory "$ROOT_DIR" --env-file "$ENV_FILE" exec -T api \
  python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health')"

