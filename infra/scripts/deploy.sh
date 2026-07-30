#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT_DIR/.env}"
new_tag="${1:-}"

if [[ ! "$new_tag" =~ ^[0-9a-f]{7,40}$ ]]; then
  echo "Usage: $0 <git-sha-image-tag>" >&2
  exit 1
fi
if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing environment file: $ENV_FILE" >&2
  exit 1
fi

set -a
source "$ENV_FILE"
set +a
previous_tag="${IMAGE_TAG:-}"
if [[ -z "$previous_tag" ]]; then
  echo "IMAGE_TAG must be set in $ENV_FILE" >&2
  exit 1
fi

set_image_tag() {
  local value="$1"
  local temporary="$ENV_FILE.tmp"
  awk -v value="$value" '
    BEGIN { found=0 }
    /^IMAGE_TAG=/ { print "IMAGE_TAG=" value; found=1; next }
    { print }
    END { if (!found) print "IMAGE_TAG=" value }
  ' "$ENV_FILE" > "$temporary"
  mv -- "$temporary" "$ENV_FILE"
}

rollback() {
  echo "Deployment failed; restoring image tag $previous_tag" >&2
  set_image_tag "$previous_tag"
  IMAGE_TAG="$previous_tag" docker compose --project-directory "$ROOT_DIR" \
    --env-file "$ENV_FILE" pull api worker web || true
  IMAGE_TAG="$previous_tag" docker compose --project-directory "$ROOT_DIR" \
    --env-file "$ENV_FILE" up -d || true
}
trap rollback ERR

"$ROOT_DIR/infra/scripts/backup.sh" >/dev/null
set_image_tag "$new_tag"
export IMAGE_TAG="$new_tag"

docker compose --project-directory "$ROOT_DIR" --env-file "$ENV_FILE" pull api worker web
docker compose --project-directory "$ROOT_DIR" --env-file "$ENV_FILE" run --rm api \
  alembic upgrade head
docker compose --project-directory "$ROOT_DIR" --env-file "$ENV_FILE" up -d

docker compose --project-directory "$ROOT_DIR" --env-file "$ENV_FILE" exec -T api \
  python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health')"
curl --fail --silent --show-error --retry 12 --retry-delay 5 \
  "https://$APP_DOMAIN/api/v1/health" >/dev/null

trap - ERR
echo "Deployed $new_tag"

