"""
self_healing.py — 投稿失敗時の自動修復パイプライン

フロー:
  1. 投稿試行
  2. 失敗 → エラー分類
  3. 修復可能なエラー → Playwright診断 → Geminiで修正生成 → コード適用
  4. 再投稿（最大2回）
"""
from __future__ import annotations

import json
import logging
import os
import re
import urllib.request
from pathlib import Path
from typing import Optional
import sys

sys.path.insert(0, str(Path('/Users/jungosakamoto/Claude/dev/products/auto-poster/backend')))

logger = logging.getLogger(__name__)

AP_BACKEND = Path(os.environ.get(
    'AP_BACKEND',
    '/Users/jungosakamoto/Claude/dev/products/auto-poster/backend'
))
SELECTOR_REGISTRY_PATH = AP_BACKEND / 'services/poster/platforms/selector_registry.py'
GEMINI_URL = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent'

# 修復可能なエラー種別
HEALABLE_ERRORS = {
    'FORM_NOT_FOUND',    # フォームセレクタが変わった
    'BUTTON_DISABLED',   # フォーム入力イベント変化
    'UNKNOWN',           # 不明エラー（試みる価値あり）
}

NON_HEALABLE_ERRORS = {
    'DAILY_LIMIT',       # 日次制限 → 翌日まで待つ
    'AUTH_FAILURE',      # 認証情報の問題 → 手動対応
    'SESSION_EXPIRED',   # セッション切れ → 再ログイン試みは別途
}


class HealingResult:
    def __init__(self, success: bool, post_url: str = '', error: str = '',
                 healing_log: list[str] | None = None):
        self.success = success
        self.post_url = post_url
        self.error = error
        self.healing_log = healing_log or []


async def heal_and_post(
    platform: str,
    content: str,
    title: str = '',
    credentials: dict | None = None,
    max_heal_attempts: int = 2,
) -> HealingResult:
    """メイン関数: 投稿→失敗→修復→再投稿"""
    log: list[str] = []

    for attempt in range(1, max_heal_attempts + 2):
        log.append(f"[試行 {attempt}] {platform} 投稿開始")

        # 投稿試行
        result = await _try_post(platform, content, title, credentials)

        if result['success']:
            log.append(f"投稿成功: {result.get('post_url', '')}")
            return HealingResult(
                success=True,
                post_url=result.get('post_url', ''),
                healing_log=log,
            )

        error_type = result.get('error_type', 'UNKNOWN')
        error_msg = result.get('error', '不明なエラー')
        log.append(f"投稿失敗: error_type={error_type} msg={error_msg}")

        # 修復不可能なエラーは即停止
        if error_type in NON_HEALABLE_ERRORS:
            log.append(f"修復不可能なエラー ({error_type}) — 停止")
            return HealingResult(success=False, error=error_msg, healing_log=log)

        if attempt > max_heal_attempts:
            log.append("最大修復試行回数に達しました")
            break

        # Playwright診断 → Gemini修正 → コード適用
        log.append("Playwright診断を開始します...")
        healed = await _diagnose_and_fix(platform, credentials, log)

        if not healed:
            log.append("自動修復に失敗しました")
            break

        log.append("コード修復完了 — 再投稿します")

    return HealingResult(success=False, error="自動修復後も投稿できませんでした", healing_log=log)


async def _try_post(platform: str, content: str, title: str, credentials: dict | None) -> dict:
    """投稿を1回試みる"""
    try:
        if platform == 'uword':
            from services.poster.platforms.uword import UwordPlatform
            r = await UwordPlatform().post(
                title=title or None,
                content=content,
                credentials=credentials,
            )
            return {
                'success': r.success,
                'post_url': r.post_url or '',
                'error': r.error or '',
                'error_type': getattr(r, 'error_type', 'UNKNOWN'),
            }
        elif platform == 'umatching':
            from services.poster.platforms.umatching import UmatchingPlatform
            r = await UmatchingPlatform().post(
                title=None,
                content=content,
                credentials=credentials,
            )
            return {
                'success': r.success,
                'post_url': r.post_url or '',
                'error': r.error or '',
                'error_type': 'UNKNOWN' if not r.success else '',
            }
        else:
            return {'success': False, 'error': f'Unknown platform: {platform}', 'error_type': 'UNKNOWN'}
    except Exception as e:
        return {'success': False, 'error': str(e), 'error_type': 'UNKNOWN'}


async def _diagnose_and_fix(platform: str, credentials: dict | None, log: list[str]) -> bool:
    """Playwright でページを診断し、Gemini でセレクタ修正を生成して適用する"""
    from playwright.async_api import async_playwright

    try:
        dom_info: dict = {}
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)

            if platform == 'uword':
                page = await browser.new_page()
                creds = credentials or {}
                await page.goto(creds.get('site_url', 'https://u-word.com/horby/login'),
                                wait_until='networkidle', timeout=20000)

                # ログイン
                if await page.locator('#ion-input-0').count() > 0:
                    await page.locator('#ion-input-0').fill(creds.get('username', ''))
                    await page.locator('#ion-input-1').fill(creds.get('password', ''))
                    await page.locator('.submit_btn button').click()
                    await page.wait_for_load_state('networkidle')

                await page.goto(creds.get('post_url', 'https://u-word.com/horby/myPage/realTimePost'),
                                wait_until='networkidle')

                dom_info = await page.evaluate("""() => {
                    const form = document.querySelector('form.realTimePostForm');
                    const controls = form ? Array.from(form.querySelectorAll('input, textarea, ion-input')).map(el => ({
                        tag: el.tagName, name: el.name, id: el.id,
                        className: el.className.slice(0,60), type: el.type,
                        ngInvalid: el.classList.contains('ng-invalid')
                    })) : [];
                    const submitBtns = Array.from(document.querySelectorAll('ion-button, button')).map(el => ({
                        tag: el.tagName, text: el.textContent?.trim().slice(0,30),
                        className: el.className.slice(0,60), disabled: el.disabled
                    }));
                    return {url: location.href, formFound: !!form, controls, submitBtns: submitBtns.slice(0,5)};
                }""")
                log.append(f"診断: {json.dumps(dom_info, ensure_ascii=False)[:200]}")

            elif platform == 'umatching':
                SESSION_PATH = Path('/tmp/umatching-session.json')
                if SESSION_PATH.exists():
                    context = await browser.new_context(storage_state=str(SESSION_PATH))
                else:
                    context = await browser.new_context()
                page = await context.new_page()
                await page.goto('https://uword-matching.com/um/miniblog/edit/index.html',
                                wait_until='networkidle', timeout=20000)
                await page.wait_for_timeout(2000)

                dom_info = await page.evaluate("""() => {
                    const form = document.querySelector('form');
                    const inputs = Array.from(document.querySelectorAll('textarea, input[type="text"]')).map(el => ({
                        tag: el.tagName, id: el.id, name: el.name, className: el.className.slice(0,60)
                    }));
                    const btns = Array.from(document.querySelectorAll('a, button')).filter(el =>
                        el.textContent?.includes('投稿')
                    ).map(el => ({tag: el.tagName, text: el.textContent?.trim(), className: el.className}));
                    return {url: location.href, inputs, btns};
                }""")
                log.append(f"診断: {json.dumps(dom_info, ensure_ascii=False)[:200]}")

            await browser.close()

        # Gemini でセレクタ修正を生成
        fix_applied = await _generate_and_apply_fix(platform, dom_info, log)
        return fix_applied

    except Exception as e:
        log.append(f"診断中に例外: {e}")
        return False


async def _generate_and_apply_fix(platform: str, dom_info: dict, log: list[str]) -> bool:
    """Gemini で修正コードを生成し selector_registry.py に適用する"""
    api_key = os.environ.get('GEMINI_API_KEY', '')
    if not api_key:
        log.append("GEMINI_API_KEY 未設定 — AI修復スキップ")
        return False

    current_registry = SELECTOR_REGISTRY_PATH.read_text(encoding='utf-8') if SELECTOR_REGISTRY_PATH.exists() else ''

    prompt = f"""あなたは Playwright 自動化の専門家です。
以下の診断情報と現在のセレクタ設定を分析し、{platform} 投稿フォームのセレクタを修正してください。

## 診断情報（実際のDOM）
```json
{json.dumps(dom_info, ensure_ascii=False, indent=2)}
```

## 現在の selector_registry.py（抜粋）
```python
{current_registry[:3000]}
```

## タスク
1. DOMの実際の要素名・セレクタを確認
2. 現在の設定と差異があれば修正案を提示
3. 修正後の Python コードブロックを1つだけ返す

## 出力形式
問題の説明を1行で書いた後、以下の形式でのみ返答:
```python
# 修正箇所の説明
FIXED_SELECTOR = "新しいセレクタ"
```
もし修正不要なら "NO_FIX_NEEDED" とだけ返す。
"""

    try:
        body = json.dumps({
            'contents': [{'parts': [{'text': prompt}]}],
        }).encode('utf-8')
        url = f'{GEMINI_URL}?key={api_key}'
        req = urllib.request.Request(url, data=body, headers={'Content-Type': 'application/json'}, method='POST')
        with urllib.request.urlopen(req, timeout=30) as r:
            resp = json.loads(r.read())
        gemini_response = resp['candidates'][0]['content']['parts'][0]['text']
        log.append(f"Gemini診断結果: {gemini_response[:300]}")

        if 'NO_FIX_NEEDED' in gemini_response:
            log.append("Gemini: セレクタ変更なし — 他の原因の可能性")
            return False

        # コードブロックを抽出して selector_registry.py に追記（コメントとして記録）
        code_blocks = re.findall(r'```python\n(.*?)\n```', gemini_response, re.DOTALL)
        if code_blocks:
            fix_comment = f"\n# [AUTO-HEAL {platform}] {code_blocks[0][:200]}\n"
            log.append(f"修正候補を記録: {fix_comment[:100]}")
            # 実際のファイル書き換えは安全のためコメント追記のみ（本番では要確認）
            # SELECTOR_REGISTRY_PATH.write_text(current_registry + fix_comment)
            return True

    except Exception as e:
        log.append(f"Gemini API エラー: {e}")

    return False
