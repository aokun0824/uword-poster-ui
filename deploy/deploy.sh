#!/bin/bash
# U-Word 投稿管理ツール VPS デプロイスクリプト
# 使い方: ./deploy/deploy.sh
set -e

VPS="root@72.61.119.101"
APP_DIR="/root/uword-poster-ui"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FRONTEND_DIR="$SCRIPT_DIR/../frontend"
BACKEND_DIR="$SCRIPT_DIR/../backend"
DEPLOY_DIR="$SCRIPT_DIR"

echo "=== フロントエンドビルド ==="
cd "$FRONTEND_DIR"
VITE_API_BASE="https://uword.kingjungobot.cloud/api" npm run build

echo "=== VPS へ転送 ==="
# バックエンド
ssh "$VPS" "mkdir -p $APP_DIR/backend"
rsync -avz --exclude='__pycache__' --exclude='*.pyc' --exclude='.env' \
  "$BACKEND_DIR/" "$VPS:$APP_DIR/backend/"

# フロントエンド（ビルド済み）→ /var/www/uword（nginx 標準パス、/root 配下は 700 で配信不可のため）
ssh "$VPS" "mkdir -p /var/www/uword"
rsync -avz "$FRONTEND_DIR/dist/" "$VPS:/var/www/uword/"
ssh "$VPS" "chown -R www-data:www-data /var/www/uword && chmod -R a+rX /var/www/uword"

echo "=== VPS 設定 ==="
# Gemini APIキーをローカルKeychainから取得
GEMINI_KEY="$(security find-generic-password -s GEMINI_API_KEY -w 2>/dev/null || true)"

ssh "$VPS" bash << REMOTE
set -e
cd /root/uword-poster-ui/backend

# venv 作成（存在する場合はスキップ）
if [ ! -d venv ]; then
  echo "venv を作成します..."
  python3 -m venv venv
fi

# 依存パッケージインストール
echo "依存パッケージをインストール中..."
venv/bin/pip install -r requirements.txt -q

# .env 作成（初回のみ）
if [ ! -f .env ]; then
  cat > .env << ENV
AP_BACKEND=/root/Claude/dev/products/auto-poster/backend
ALLOWED_ORIGINS=https://uword.kingjungobot.cloud
GEMINI_API_KEY=${GEMINI_KEY}
UWORD_SETTINGS_PATH=/root/uword-poster-ui/backend/auto_settings.json
UWORD_BOILERPLATE_PATH=/root/uword-poster-ui/backend/boilerplate.json
UWORD_REPORTS_DIR=/root/uword-poster-ui/reports/weekly
UWORD_SCHEDULER_DB=/root/uword-poster-ui/backend/scheduler_jobs.db
ENV
  echo ".env 作成済み"
else
  # 既存.envのGEMINI_API_KEYを更新（空でない場合）
  if [ -n "${GEMINI_KEY}" ]; then
    sed -i "s|^GEMINI_API_KEY=.*|GEMINI_API_KEY=${GEMINI_KEY}|" .env
    echo "GEMINI_API_KEY 更新済み"
  fi
fi

# systemd サービス更新
cp /root/uword-poster-ui/deploy/uword-poster.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable uword-poster
systemctl restart uword-poster
sleep 2
systemctl is-active uword-poster && echo "backend 起動OK"
REMOTE

echo "=== nginx 設定 ==="
scp "$DEPLOY_DIR/nginx-uword.conf" "$VPS:/etc/nginx/sites-available/uword"
ssh "$VPS" "ln -sf /etc/nginx/sites-available/uword /etc/nginx/sites-enabled/uword; nginx -t && systemctl reload nginx"

echo "=== SSL 証明書 ==="
ssh "$VPS" "certbot --nginx -d uword.kingjungobot.cloud --non-interactive --agree-tos -m kodawarimaxjp@gmail.com 2>/dev/null || echo 'SSL already configured or skipped'"

echo ""
echo "✅ デプロイ完了"
echo "🌐 https://uword.kingjungobot.cloud"
