#!/bin/bash
# U-Word 投稿管理ツール 起動スクリプト

ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "🚀 バックエンド起動中 (port 5201)..."
cd "$ROOT/backend"
python3 -m uvicorn main:app --host 0.0.0.0 --port 5201 --reload &
BACKEND_PID=$!

echo "🚀 フロントエンド起動中 (port 5200)..."
cd "$ROOT/frontend"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "✅ 起動完了"
echo "   http://localhost:5200"
echo ""
echo "停止するには Ctrl+C"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo '停止しました'" EXIT INT TERM
wait
