#!/usr/bin/env bash
set -euo pipefail

DB_SRC="/home/oracle/fitness-bot/fitness.db"
BACKUP_DIR="/home/oracle/backups/fitness-bot"
DATE=$(date +%Y-%m-%d_%H-%M)
BACKUP_FILE="$BACKUP_DIR/fitness_${DATE}.db"

mkdir -p "$BACKUP_DIR"
sqlite3 "$DB_SRC" ".backup '$BACKUP_FILE'"
gzip "$BACKUP_FILE"
find "$BACKUP_DIR" -name "fitness_*.db.gz" -mtime +30 -delete

echo "Backup OK: ${BACKUP_FILE}.gz"
