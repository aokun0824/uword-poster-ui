#!/bin/bash
# U-Word 投稿管理ツール — 設定バックアップスクリプト
# 使い方: ./backup.sh
# launchd で週次実行推奨

set -e
BACKUP_DIR="$(dirname "$0")/backups/$(date +%Y-%m-%d)"
mkdir -p "$BACKUP_DIR"

# バックアップ対象
BACKEND_DIR="$(dirname "$0")/backend"
FILES=(
  "$BACKEND_DIR/auto_settings.json"
  "$BACKEND_DIR/boilerplate.json"
  "$BACKEND_DIR/scheduler_jobs.db"
)

for f in "${FILES[@]}"; do
  if [ -f "$f" ]; then
    cp "$f" "$BACKUP_DIR/"
    echo "Backed up: $(basename $f)"
  else
    echo "Not found: $f"
  fi
done

# 7日より古いバックアップを削除
find "$(dirname "$0")/backups" -maxdepth 1 -type d -mtime +7 -exec rm -rf {} + 2>/dev/null || true

echo "Backup complete: $BACKUP_DIR"
