#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
backup_root="${BACKUP_ROOT:-$repo_dir/backups}"
retention_days="${BACKUP_RETENTION_DAYS:-7}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_dir="$backup_root/$timestamp"

if [[ -z "$backup_root" || "$backup_root" == "/" || "$backup_root" == "$repo_dir" ]]; then
  echo "Refusing unsafe BACKUP_ROOT: $backup_root" >&2
  exit 1
fi

for command_name in docker gzip find; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "Required command is unavailable: $command_name" >&2
    exit 1
  fi
done

mkdir -p "$backup_dir"
chmod 700 "$backup_root" "$backup_dir"

docker exec pg_airlines \
  pg_dump --username=airlines --dbname=airlines_db --format=custom \
  > "$backup_dir/postgresql.dump"

docker exec mongo_airlines \
  mongodump --archive --gzip \
  > "$backup_dir/mongodb.archive.gz"

# Neo4j Community dump requires the database to be offline. The temporary
# container mounts the existing data volume while the application container is
# stopped, then the original container is restarted immediately.
docker stop neo4j_airlines >/dev/null
trap 'docker start neo4j_airlines >/dev/null 2>&1 || true' EXIT
docker run --rm \
  --volumes-from neo4j_airlines \
  --volume "$backup_dir:/backups" \
  --entrypoint neo4j-admin \
  neo4j:5 \
  database dump neo4j --to-path=/backups
docker start neo4j_airlines >/dev/null
trap - EXIT

(
  cd "$backup_dir"
  shasum -a 256 postgresql.dump mongodb.archive.gz neo4j.dump > SHA256SUMS
)

find "$backup_root" \
  -mindepth 1 \
  -maxdepth 1 \
  -type d \
  -name "20??????T??????Z" \
  -mtime "+$retention_days" \
  -exec rm -r -- {} +

echo "Backup completed: $backup_dir"
