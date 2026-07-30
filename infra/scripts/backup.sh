#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT_DIR/.env}"
BACKUP_DIR="${BACKUP_DIR:-$ROOT_DIR/backups}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing environment file: $ENV_FILE" >&2
  exit 1
fi

case "$(cd "$(dirname "$BACKUP_DIR")" && pwd)/$(basename "$BACKUP_DIR")" in
  /|"$ROOT_DIR")
    echo "Refusing unsafe backup directory: $BACKUP_DIR" >&2
    exit 1
    ;;
esac

set -a
source "$ENV_FILE"
set +a

mkdir -p "$BACKUP_DIR/daily" "$BACKUP_DIR/weekly" "$BACKUP_DIR/monthly"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
temporary="$BACKUP_DIR/.techgrowth-$timestamp.dump.tmp"
daily="$BACKUP_DIR/daily/techgrowth-$timestamp.dump"

cleanup() {
  rm -f -- "$temporary"
}
trap cleanup EXIT

docker compose --project-directory "$ROOT_DIR" --env-file "$ENV_FILE" exec -T db \
  pg_dump --format=custom --no-owner --no-privileges \
  --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" > "$temporary"

test -s "$temporary"
mv -- "$temporary" "$daily"

if [[ "$(date -u +%u)" == "7" ]]; then
  cp -- "$daily" "$BACKUP_DIR/weekly/$(basename "$daily")"
fi
if [[ "$(date -u +%d)" == "01" ]]; then
  cp -- "$daily" "$BACKUP_DIR/monthly/$(basename "$daily")"
fi

prune_to_count() {
  local directory="$1"
  local keep="$2"
  mapfile -t files < <(find "$directory" -maxdepth 1 -type f -name 'techgrowth-*.dump' -print | sort)
  local remove_count=$(( ${#files[@]} - keep ))
  if (( remove_count > 0 )); then
    for (( index=0; index<remove_count; index++ )); do
      rm -f -- "${files[$index]}"
    done
  fi
}

prune_to_count "$BACKUP_DIR/daily" 7
prune_to_count "$BACKUP_DIR/weekly" 4
prune_to_count "$BACKUP_DIR/monthly" 6

echo "$daily"

