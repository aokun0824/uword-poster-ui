# U-Word 投稿管理ツール

U-Word（リアルタイム速報）と Umatching（ミニブログ）への自動投稿・管理ダッシュボード。

## 構成

| コンポーネント | 技術 | ポート |
|---|---|---|
| フロントエンド | Vue3 + Vite + TypeScript | 5200 |
| バックエンド | FastAPI + APScheduler | 5201 |

## 依存

- auto-poster (`/path/to/auto-poster/backend`) — DB・認証情報・投稿アダプタを参照
- Playwright（Chromium）— 投稿実行・診断

## セットアップ

### 1. 環境変数設定

```bash
cp .env.example .env
# .env を編集して AP_BACKEND を設定
```

### 2. バックエンド起動

```bash
cd backend
pip install -r requirements.txt
python3 -m uvicorn main:app --port 5201
```

### 3. フロントエンド起動

```bash
cd frontend
npm install
npm run dev   # → http://localhost:5200
```

## 機能

- **投稿タブ**: 手動投稿・AI記事生成（URL/トピック）・画像アップロード・定型文設定
- **自動設定タブ**: 曜日×時刻スケジュール・記事生成ソース管理
- **週次レビュータブ**: 集客スコア（Gemini採点）・AI評価詳細
- **診断タブ**: Playwrightによるページ状態・セッション有効性確認
- **ログ詳細タブ**: 全投稿履歴・エラー詳細

## ヘルスチェック

`GET http://localhost:5201/health` でAPScheduler・DB・APIキー状態を確認。

## バックアップ

`./backup.sh` で `auto_settings.json`・`boilerplate.json`・`scheduler_jobs.db` を `backups/` に保存。
