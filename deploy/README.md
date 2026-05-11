# VPS デプロイ手順

## 前提
- VPS: root@72.61.119.101
- ドメイン: uword.kingjungobot.cloud → 72.61.119.101 のAレコード追加が必要

## デプロイ

```bash
chmod +x deploy/deploy.sh
./deploy/deploy.sh
```

## 初回セットアップ（VPS側）

```bash
# GEMINI_API_KEY を設定
ssh root@72.61.119.101
nano /root/uword-poster-ui/backend/.env
# GEMINI_API_KEY=あなたのキー を設定
systemctl restart uword-poster
```

## 確認

```bash
# バックエンド
curl https://uword.kingjungobot.cloud/health

# フロントエンド
open https://uword.kingjungobot.cloud
```
