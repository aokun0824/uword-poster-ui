# U-Word 投稿管理ツール

U-Word（リアルタイム速報・ミニブログ）への投稿を自動化する管理ツール。

AI（Gemini / LLaMA）でコンテンツを自動生成し、Playwright で U-Word に投稿します。

## 機能

- **手動投稿**: タイトル・本文を入力してワンクリック投稿
- **AI 生成**: キーワードとトーンを指定してコンテンツを自動生成
- **自動スケジュール**: 毎日 08:30 / 19:30 に自動投稿（APScheduler）
- **今日の投稿状況**: リアルタイム速報・ミニブログそれぞれの残枠を表示
- **週次レビュー**: 投稿パフォーマンスの週次レポート
- **AIキャラクターアシスタント**: 好きなキャラを選んでSNS投稿の相談ができるチャット機能

## スクリーンショット

| 投稿タブ | 設定タブ |
|---------|---------|
| 今日の投稿状況バッジ・AI生成・投稿フォーム | ログイン情報をここで管理 |

## セットアップ

### 前提条件

- Node.js 20+
- Python 3.11+
- [auto-poster](https://github.com/kodawarimax/auto-poster) リポジトリ（認証情報・DB管理）

### 1. クローン

```bash
git clone https://github.com/kodawarimax/uword-poster-ui.git
cd uword-poster-ui

# auto-poster も同階層にクローン
git clone https://github.com/kodawarimax/auto-poster.git
```

### 2. 環境変数の設定

```bash
cp backend/.env.example backend/.env
# backend/.env を編集して以下を設定
```

**backend/.env の必須項目：**

```
AP_BACKEND=/path/to/auto-poster/backend   # auto-posterのパス

GEMINI_API_KEY=your_gemini_api_key_here   # AIチャット機能に必要
```

**Gemini API キーの取得方法（無料）：**

1. [Google AI Studio](https://aistudio.google.com) にアクセス
2. Googleアカウントでログイン
3. 「Get API key」→「Create API key」をクリック
4. 表示されたキーを `GEMINI_API_KEY=` の後に貼り付ける

> キーを取得しない場合でも、チャット機能以外は通常通り使えます。

### 3. バックエンド起動

```bash
cd backend
pip install -r requirements.txt
playwright install chromium
uvicorn main:app --port 5201 --reload
```

### 4. フロントエンド起動

```bash
cd frontend
npm install
npm run dev
```

ブラウザで http://localhost:5200 を開く。

---

### Docker で起動（推奨）

```bash
cp backend/.env.example backend/.env
docker compose up --build
```

http://localhost:5200 を開く。

## 初期設定

1. **設定タブ** を開く
2. リアルタイム速報・ミニブログそれぞれの U-Word アカウント情報を入力
3. 「保存（ブラウザに記憶）」をクリック

## 自動投稿の有効化

自動設定タブ → スケジュール追加 → `08:30, 19:30` を設定

## 技術スタック

| 層 | 技術 |
|----|------|
| フロントエンド | Vue 3 + Vite + TypeScript |
| バックエンド | FastAPI + APScheduler |
| 投稿自動化 | Playwright (Chromium) |
| AI 生成 | OpenRouter (Gemini / LLaMA) |

## ヘルスチェック

```bash
curl http://localhost:5201/health
```

APScheduler・DB・APIキー状態を確認できます。

## バックアップ

```bash
./backup.sh
```

`auto_settings.json`・`boilerplate.json`・`scheduler_jobs.db` を `backups/` に保存します。

## ライセンス

MIT
