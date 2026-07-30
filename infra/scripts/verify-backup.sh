#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT_DIR/.env}"
BACKUP_DIR="${BACKUP_DIR:-$ROOT_DIR/backups}"
latest="$(find "$BACKUP_DIR/daily" -maxdepth 1 -type f -name 'techgrowth-*.dump' -print | sort | tail -n 1)"

if [[ ! -f "$latest" ]]; then
  echo "No daily backup is available" >&2
  exit 1
fi

set -a
source "$ENV_FILE"
set +a
verification_db="techgrowth_verify_$(date -u +%Y%m%d%H%M%S)"

cleanup() {
  docker compose --project-directory "$ROOT_DIR" --env-file "$ENV_FILE" exec -T db \
    dropdb --force --if-exists --username "$POSTGRES_USER" "$verification_db" >/dev/null
}
trap cleanup EXIT

docker compose --project-directory "$ROOT_DIR" --env-file "$ENV_FILE" exec -T db \
  createdb --username "$POSTGRES_USER" "$verification_db"
docker compose --project-directory "$ROOT_DIR" --env-file "$ENV_FILE" exec -T db \
  pg_restore --exit-on-error --no-owner --no-privileges \
  --username "$POSTGRES_USER" --dbname "$verification_db" < "$latest"

table_count="$(docker compose --project-directory "$ROOT_DIR" --env-file "$ENV_FILE" \
  exec -T db psql --tuples-only --no-align --username "$POSTGRES_USER" \
  --dbname "$verification_db" \
  --command "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';")"

if [[ "$table_count" -lt 10 ]]; then
  echo "Backup integrity check failed: only $table_count public tables" >&2
  exit 1
fi

echo "Verified $(basename "$latest") with $table_count public tables"

