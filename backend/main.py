"""U-Word 投稿専用 API — port 5201"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Form, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.triggers.cron import CronTrigger
from typing import Literal, Optional
import asyncio
import sys
import json
import shutil
import tempfile
import os
import sqlite3
import logging
import re as _re
import ipaddress
from pathlib import Path
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()


@asynccontextmanager
async def lifespan(app):
    scheduler.start()
    await _reload_jobs()
    yield
    scheduler.shutdown()


# 環境変数から設定（デフォルトは現行パス）
AP_BACKEND = Path(os.environ.get(
    'AP_BACKEND',
    '/Users/jungosakamoto/Claude/dev/products/auto-poster/backend'
))
# Load AP_BACKEND .env once at startup (override=False: don't overwrite already-set vars)
_ap_env = AP_BACKEND / '.env'
if _ap_env.exists():
    load_dotenv(_ap_env, override=False)
SETTINGS_PATH = Path(os.environ.get(
    'UWORD_SETTINGS_PATH',
    '/Users/jungosakamoto/Claude/dev/products/uword-poster-ui/backend/auto_settings.json'
))

# Valid platform identifiers (used for input validation)
_VALID_PLATFORMS = {"uword", "umatching", "facebook", "instagram", "threads", "note", "x_twitter", "linkedin"}
BOILERPLATE_PATH = Path(os.environ.get(
    'UWORD_BOILERPLATE_PATH',
    '/Users/jungosakamoto/Claude/dev/products/uword-poster-ui/backend/boilerplate.json'
))
REPORTS_DIR = Path(os.environ.get(
    'UWORD_REPORTS_DIR',
    '/Users/jungosakamoto/Claude/dev/products/auto-poster/reports/weekly'
))
_SCHEDULER_DB = os.environ.get(
    'UWORD_SCHEDULER_DB',
    '/Users/jungosakamoto/Claude/dev/products/uword-poster-ui/backend/scheduler_jobs.db'
)

sys.path.insert(0, str(AP_BACKEND))

_logger = logging.getLogger(__name__)

app = FastAPI(lifespan=lifespan)

_allowed_origins = os.environ.get(
    'ALLOWED_ORIGINS', 'http://localhost:5200,http://127.0.0.1:5200'
).split(',')
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

scheduler = AsyncIOScheduler(
    jobstores={'default': SQLAlchemyJobStore(url=f'sqlite:///{_SCHEDULER_DB}')},
    timezone='Asia/Tokyo'
)

# 最後の投稿パラメータを記憶（リトライ・修復用）
_last_post: dict = {}

_ALLOWED_IMAGE_SUFFIXES = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}


# ──────────────────────────────────────────────────────────
# セキュリティヘルパー
# ──────────────────────────────────────────────────────────

def _validate_url(url: str) -> bool:
    """SSRF対策: https スキームのみ、プライベートIPを拒否"""
    try:
        parsed = urlparse(url)
        if parsed.scheme != 'https':
            return False
        host = parsed.hostname
        if not host:
            return False
        try:
            ip = ipaddress.ip_address(host)
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                return False
        except ValueError:
            pass  # ホスト名（ドメイン）は許可
        return True
    except Exception:
        return False


def _is_youtube_url(url: str) -> bool:
    """YouTube URL かどうか判定"""
    try:
        host = urlparse(url).hostname or ''
        return host in ('www.youtube.com', 'youtube.com', 'youtu.be', 'm.youtube.com')
    except Exception:
        return False


# ──────────────────────────────────────────────────────────
# モデル定義
# ──────────────────────────────────────────────────────────

class PostRequest(BaseModel):
    platform: Literal["uword", "umatching", "facebook", "instagram", "threads", "note", "x_twitter", "linkedin"]
    title: str = ""
    content: str
    hashtags: list[str] = []
    image_path: Optional[str] = None


class PostResponse(BaseModel):
    success: bool
    post_url: str = ""
    error: str = ""


TONE_PROMPTS = {
    "professional": {
        "label": "覚悟層・経営者向け",
        "uword_style": "覚悟ある経営者・個人事業主向け。硬派で力強いトーン。禁止語: 簡単・手軽。CTA必須。",
        "umatching_style": "真剣にビジネスを考える人向け。誠実で信頼感のあるトーン。",
        "generic_style": "覚悟ある経営者・個人事業主向け。硬派で力強いトーン。読者に行動を促すCTAを含める。禁止語: 簡単・手軽。",
    },
    "feminine": {
        "label": "女性向け・親しみやすい",
        "uword_style": "夜職女性（ホステス・キャバ嬢）向け。親しみやすく軽やか。絵文字3〜5個。「私にもできそう！」と思わせる。体験談形式。難しい言葉禁止。",
        "umatching_style": "女性が共感できる。日常的な言葉で。絵文字2〜3個。",
        "generic_style": "女性向け・親しみやすいトーン。絵文字適度に使用。体験談・感情に訴える表現。",
    },
    "casual": {
        "label": "カジュアル・体験談",
        "uword_style": "口語体。「〜してみた」「〜だった」形式。具体的な数字や体験を交える。フレンドリーで読みやすい。",
        "umatching_style": "友達に話すような口調。短い文章でテンポよく。",
        "generic_style": "口語体。「〜してみた」「〜だった」形式。具体的な体験談。フレンドリー。",
    },
    "luxury": {
        "label": "高級・上品",
        "uword_style": "品格を感じる言葉遣い。上質なサービスをイメージさせる。落ち着いた丁寧語。",
        "umatching_style": "洗練された雰囲気。品のある言葉で。",
        "generic_style": "品格ある言葉遣い。上質な雰囲気。洗練された丁寧語。",
    },
    "urgency": {
        "label": "限定感・緊迫感",
        "uword_style": "「今だけ」「限定」「残りわずか」のような緊迫感。行動を促す強いCTA。短文でインパクト重視。",
        "umatching_style": "今すぐ行動を促す。短く強いメッセージ。",
        "generic_style": "「今だけ」「限定」など緊迫感。強いCTA。短文でインパクト。",
    },
    "senior_solo": {
        "label": "50代〜個人事業主向け",
        "uword_style": (
            "50代以降で自分のペースで個人事業を営んでいる方向け。"
            "「AIは若い人のもの」という先入観を優しく崩す。"
            "難しい言葉を一切使わない。スマホで使える・パソコン不要などの安心感を添える。"
            "「私にもできるかも」と思わせる穏やかで温かいトーン。"
            "具体的な日常シーン（見積書作り・お客様への返信・SNS投稿など）で例示する。"
            "絵文字は1〜2個だけ、落ち着いた雰囲気を保つ。"
        ),
        "umatching_style": (
            "50代以降の個人事業主向け。丁寧語。日常業務でのAI活用を具体的に。"
            "難しい言葉なし。安心感・手軽さを前面に。"
        ),
        "generic_style": "50代以降の個人事業主向け。難しい言葉なし。安心感・手軽さを前面に。日常シーンで例示。絵文字1〜2個。",
    },
}


PLATFORM_CONFIGS = {
    "uword":     {"name": "リアルタイム速報", "icon": "📰", "char_limit": 400,   "has_poster": True,  "has_title": True},
    "umatching": {"name": "ミニブログ",       "icon": "📝", "char_limit": 300,   "has_poster": True,  "has_title": False},
    "facebook":  {"name": "Facebook",         "icon": "🔵", "char_limit": 2000,  "has_poster": False, "has_title": False},
    "instagram": {"name": "Instagram",        "icon": "📸", "char_limit": 2200,  "has_poster": False, "has_title": False},
    "threads":   {"name": "Threads",          "icon": "🧵", "char_limit": 500,   "has_poster": True, "has_title": False},
    "note":      {"name": "Note",             "icon": "📖", "char_limit": 10000, "has_poster": True, "has_title": True},
    "x_twitter": {"name": "X (Twitter)",      "icon": "✖️",  "char_limit": 280,   "has_poster": True, "has_title": False},
    "linkedin":  {"name": "LinkedIn",         "icon": "💼", "char_limit": 3000,  "has_poster": True, "has_title": True},
}


class GenerateRequest(BaseModel):
    source_type: str  # "url" or "topic"
    source: str       # URL or topic text
    platform: str     # "uword" or "umatching"
    tone: str = "professional"  # トーン設定
    custom_style: str = ""      # カスタム指示
    cta_url: str = ""
    cta_text: str = ""


class GenerateResponse(BaseModel):
    title: str = ""
    content: str
    hashtags: list[str] = []


class DeriveRequest(BaseModel):
    note_content: str
    note_title: str = ''
    cta_url: str = ""
    cta_text: str = ""
    note_url: str = ""
    platforms: list[str] = ['x_twitter', 'threads', 'instagram', 'facebook', 'linkedin', 'uword', 'umatching']


class DeriveResult(BaseModel):
    platform: str
    title: str = ''
    content: str
    hashtags: list[str] = []


class DeriveResponse(BaseModel):
    results: list[DeriveResult]


class SummarizeRequest(BaseModel):
    url: str

class SummarizeResponse(BaseModel):
    title: str = ""
    summary: str
    source_type: str  # "youtube" or "article"


class ImageGenRequest(BaseModel):
    content: str = ""       # 投稿テキスト（auto-prompt生成に使用）
    custom_prompt: str = "" # ユーザーが入力した画像プロンプト（優先）
    platform: str = "general"

class ImageGenResponse(BaseModel):
    image_data: str   # base64エンコード済み画像
    mime_type: str = "image/png"
    used_prompt: str = ""  # 実際に使用されたプロンプト


class Boilerplate(BaseModel):
    uword_footer: str = ""
    umatching_footer: str = ""
    fixed_url: str = ""
    fixed_hashtags: list[str] = []


class SourceItem(BaseModel):
    type: str        # "url" | "topic"
    value: str
    enabled: bool = True


class GenerationConfig(BaseModel):
    platform: Literal["uword", "umatching"]
    sources: list[SourceItem] = []
    style_note: str = ""


class ScheduleEntry(BaseModel):
    platform: Literal["uword", "umatching"]
    days: list[str]  # ["mon","tue","wed","thu","fri","sat","sun"]
    times: list[str] # ["08:30", "19:30"]
    enabled: bool = True


class AutoSettings(BaseModel):
    generation: list[GenerationConfig] = []
    schedules: list[ScheduleEntry] = []


# ──────────────────────────────────────────────────────────
# Gemini API 共通呼び出し
# ──────────────────────────────────────────────────────────

async def _call_gemini(prompt: str) -> dict:
    """Gemini API を呼び出して JSON レスポンスを返す"""
    import urllib.request
    api_key = os.environ.get('GEMINI_API_KEY', '')
    if not api_key:
        raise ValueError('GEMINI_API_KEY not set')
    url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}'
    body = json.dumps({
        'contents': [{'parts': [{'text': prompt}]}],
        'generationConfig': {'responseMimeType': 'application/json'}
    }).encode('utf-8')
    req = urllib.request.Request(url, data=body, headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=30) as r:
        resp = json.loads(r.read())
    text = resp['candidates'][0]['content']['parts'][0]['text']
    result = json.loads(text)
    if isinstance(result, list):
        result = result[0] if result else {}
    return result


# ──────────────────────────────────────────────────────────
# ヘルスチェック
# ──────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """ヘルスチェック: APScheduler・DB・Geminiキー確認"""
    db_ok = False
    try:
        with sqlite3.connect(str(AP_BACKEND / 'data' / 'autopost.db')) as conn:
            conn.execute("SELECT 1")
        db_ok = True
    except Exception as e:
        _logger.warning("health db check failed: %s", e)
    return {
        "status": "ok",
        "scheduler_jobs": len(scheduler.get_jobs()),
        "db": db_ok,
        "gemini_key_set": bool(os.environ.get('GEMINI_API_KEY')),
    }


# ──────────────────────────────────────────────────────────
# 自動設定 CRUD & スケジューラ
# ──────────────────────────────────────────────────────────

def _load_settings() -> AutoSettings:
    if SETTINGS_PATH.exists():
        return AutoSettings(**json.loads(SETTINGS_PATH.read_text()))
    return AutoSettings()


def _save_settings(s: AutoSettings):
    SETTINGS_PATH.write_text(json.dumps(s.dict(), ensure_ascii=False, indent=2))


@app.get("/api/auto-settings")
async def get_auto_settings():
    return _load_settings()


@app.put("/api/auto-settings")
async def save_auto_settings(settings: AutoSettings):
    _save_settings(settings)
    await _reload_jobs()
    return {"ok": True, "jobs": len(scheduler.get_jobs())}


async def _auto_post_job(platform: str):
    """スケジュール実行: ソースからコンテンツ生成→投稿"""
    import random

    settings = _load_settings()
    gen_config = next((g for g in settings.generation if g.platform == platform), None)

    sources = [s for s in (gen_config.sources if gen_config else []) if s.enabled]
    if not sources:
        source = SourceItem(type="topic", value=f"AIと{platform}の最新活用法")
    else:
        source = random.choice(sources)

    style_note = gen_config.style_note if gen_config else ""

    if platform == "uword":
        prompt = f"""夜職・AIコンサル向けリアルタイム速報の投稿を作成してください。
参考: {source.value}
追加スタイル指示: {style_note}
要件: タイトル20〜40文字 / 本文200〜400文字 / 覚悟層ターゲット / CTA必須 / 禁止語: 簡単・手軽・お得・初心者
JSON形式: {{"title": "...", "content": "...", "hashtags": [...]}}"""
    else:
        prompt = f"""ミニブログ投稿を作成してください。
参考: {source.value}
追加スタイル指示: {style_note}
要件: 本文150〜300文字 / ハッシュタグ3〜5個
JSON形式: {{"title": "", "content": "...", "hashtags": [...]}}"""

    try:
        generated = await _call_gemini(prompt)
    except Exception as e:
        _logger.error("Auto-post generation failed: %s", e)
        return

    db_path = AP_BACKEND / 'data' / 'autopost.db'
    with sqlite3.connect(str(db_path)) as conn:
        row = conn.execute(
            "SELECT credentials FROM autopost_configs WHERE platform=? AND is_active=1 LIMIT 1",
            (platform,)
        ).fetchone()
    if not row:
        return

    load_dotenv(AP_BACKEND / '.env', override=False)
    from services.poster.encryption import decrypt_credentials
    creds = decrypt_credentials(row[0])

    merged_content, merged_hashtags = _merge_boilerplate(
        platform, generated.get('content', ''), [],
        ','.join(generated.get('hashtags', []))
    )
    if merged_hashtags:
        creds["hashtags"] = merged_hashtags
    merged = {"content": merged_content, "creds": creds}

    try:
        if platform == "uword":
            from services.poster.platforms.uword import UwordPlatform
            await UwordPlatform().post(
                title=generated.get('title'),
                content=merged["content"],
                credentials=merged["creds"],
            )
        else:
            from services.poster.platforms.umatching import UmatchingPlatform
            await UmatchingPlatform().post(
                title=None,
                content=merged["content"],
                credentials=merged["creds"],
            )
    except Exception as e:
        _logger.error("Auto-post posting failed: %s", e)


async def _reload_jobs():
    """設定からスケジューラジョブを再構築"""
    scheduler.remove_all_jobs()
    settings = _load_settings()

    for sched in settings.schedules:
        if not sched.enabled:
            continue
        days_str = ",".join(sched.days)
        for time_str in sched.times:
            try:
                hour, minute = time_str.split(":")
                job_id = f"{sched.platform}_{days_str}_{time_str}"
                scheduler.add_job(
                    _auto_post_job,
                    CronTrigger(
                        day_of_week=days_str,
                        hour=int(hour),
                        minute=int(minute),
                        timezone="Asia/Tokyo",
                    ),
                    args=[sched.platform],
                    id=job_id,
                    replace_existing=True,
                )
            except Exception as e:
                _logger.warning("Failed to add job for %s %s: %s", sched.platform, time_str, e)


@app.get("/api/scheduler/jobs")
async def list_jobs():
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({"id": job.id, "next_run": str(job.next_run_time)})
    return jobs


@app.post("/api/scheduler/run-now/{platform}")
async def run_now(platform: str):
    """即時実行（テスト用）"""
    if platform not in _VALID_PLATFORMS:
        return {"success": False, "error": f"Invalid platform: {platform}"}
    import asyncio
    asyncio.create_task(_auto_post_job(platform))
    return {"ok": True, "message": f"{platform} の自動生成・投稿を開始しました"}


# ──────────────────────────────────────────────────────────
# ヘルパー: 定型文マージ
# ──────────────────────────────────────────────────────────

def _load_boilerplate() -> Boilerplate:
    if BOILERPLATE_PATH.exists():
        return Boilerplate(**json.loads(BOILERPLATE_PATH.read_text()))
    return Boilerplate()


def _merge_boilerplate(platform: str, content: str, hashtag_list: list[str], hashtags_str: str = "") -> tuple[str, list[str]]:
    """定型文マージ。hashtags_str はカンマ区切り文字列で渡すことも可（リトライ用）。"""
    if hashtags_str:
        extra = [h.strip() for h in hashtags_str.split(',') if h.strip()]
        hashtag_list = list(set(hashtag_list + extra))
    bp = _load_boilerplate()
    footer = bp.uword_footer if platform == "uword" else bp.umatching_footer
    if footer:
        content = content + "\n\n" + footer
    if bp.fixed_url:
        content = content + "\n" + bp.fixed_url
    if bp.fixed_hashtags:
        hashtag_list = list(set(hashtag_list + bp.fixed_hashtags))
    return content, hashtag_list


# ──────────────────────────────────────────────────────────
# 既存投稿エンドポイント（JSON ボディ、定型文マージ対応）
# ──────────────────────────────────────────────────────────

@app.post("/api/post", response_model=PostResponse)
async def post_content(req: PostRequest):
    from services.poster.encryption import decrypt_credentials

    db_path = AP_BACKEND / "data" / "autopost.db"
    with sqlite3.connect(str(db_path)) as conn:
        row = conn.execute(
            "SELECT credentials FROM autopost_configs WHERE platform=? AND is_active=1 LIMIT 1",
            (req.platform,)
        ).fetchone()
    if not row:
        return PostResponse(success=False, error=f"{req.platform} の設定が見つかりません")

    creds = decrypt_credentials(row[0])
    hashtag_list = list(req.hashtags)
    if hashtag_list:
        creds["hashtags"] = hashtag_list

    # 定型文マージ
    content, hashtag_list = _merge_boilerplate(req.platform, req.content, hashtag_list)
    creds["hashtags"] = hashtag_list

    if req.platform == "uword":
        from services.poster.platforms.uword import UwordPlatform
        result = await UwordPlatform().post(
            title=req.title or None,
            content=content,
            credentials=creds,
        )
    elif req.platform == "umatching":
        from services.poster.platforms.umatching import UmatchingPlatform
        result = await UmatchingPlatform().post(
            title=None,
            content=content,
            credentials=creds,
        )
    elif req.platform in ("facebook", "instagram", "threads", "note", "x_twitter"):
        platform_name = req.platform if req.platform != "note" else "note_com"
        from services.poster.platforms.base import get_platform
        platform_obj = get_platform(platform_name)
        result = await platform_obj.post(
            title=req.title or None,
            content=content,
            image_path=req.image_path,
            credentials=creds,
        )
    elif req.platform == "linkedin":
        from services.poster.platforms.linkedin import LinkedInPlatform
        result = await LinkedInPlatform().post(
            title=req.title or None,
            content=content,
            credentials=creds,
        )
    else:
        return PostResponse(success=False, error="unknown platform")

    return PostResponse(
        success=result.success,
        post_url=result.post_url or "",
        error=result.error or "",
    )


# ──────────────────────────────────────────────────────────
# 画像付き投稿エンドポイント（FormData）
# ──────────────────────────────────────────────────────────

@app.post("/api/post-with-image")
async def post_with_image(
    platform: str = Form(...),
    title: str = Form(""),
    content: str = Form(...),
    hashtags: str = Form(""),   # カンマ区切り
    cred_username: str = Form(""),
    cred_password: str = Form(""),
    cred_site_url: str = Form(""),
    cred_post_url: str = Form(""),
    image: UploadFile = File(None)
):
    # ユーザー入力が優先、未入力なら DB フォールバック
    if cred_username and cred_password and cred_site_url:
        creds = {
            "username": cred_username,
            "password": cred_password,
            "site_url": cred_site_url,
            "post_url": cred_post_url or cred_site_url,
        }
    else:
        from services.poster.encryption import decrypt_credentials

        db_path = AP_BACKEND / "data" / "autopost.db"
        with sqlite3.connect(str(db_path)) as conn:
            row = conn.execute(
                "SELECT credentials FROM autopost_configs WHERE platform=? AND is_active=1 LIMIT 1",
                (platform,)
            ).fetchone()
        if not row:
            return {"success": False, "error": f"{platform} の設定が見つかりません。クレデンシャルを入力してください。"}
        creds = decrypt_credentials(row[0])

    # 画像ファイル検証
    if image and image.filename:
        suffix = Path(image.filename).suffix.lower()
        if suffix not in _ALLOWED_IMAGE_SUFFIXES:
            return {"success": False, "error": f"許可されていないファイル形式: {suffix}"}

    hashtag_list = [h.strip() for h in hashtags.split(',') if h.strip()]

    # 定型文マージ
    content, hashtag_list = _merge_boilerplate(platform, content, hashtag_list)
    if hashtag_list:
        creds["hashtags"] = hashtag_list

    # 最後の投稿パラメータを記憶（リトライ・修復用）
    _last_post.update({
        "platform": platform,
        "title": title,
        "content": content,
        "hashtags_str": hashtags,
        "image_path": None,  # 一時ファイルは消えるのでパスは保存しない
        "creds": creds,
    })

    # 画像を一時ファイルに保存
    image_path = None
    tmp = None
    if image and image.filename:
        suffix = Path(image.filename).suffix or '.jpg'
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        shutil.copyfileobj(image.file, tmp)
        tmp.close()
        image_path = tmp.name

    try:
        if platform == "uword":
            from services.poster.platforms.uword import UwordPlatform
            result = await UwordPlatform().post(
                title=title or None,
                content=content,
                image_path=image_path,
                credentials=creds,
            )
        elif platform == "umatching":
            from services.poster.platforms.umatching import UmatchingPlatform
            result = await UmatchingPlatform().post(
                title=None,
                content=content,
                image_path=image_path,
                credentials=creds,
            )
        else:
            return {"success": False, "error": "unknown platform"}
    finally:
        if tmp:
            os.unlink(tmp.name)

    return {"success": result.success, "post_url": result.post_url or "", "error": result.error or ""}


# ──────────────────────────────────────────────────────────
# AI コンテンツ生成エンドポイント
# ──────────────────────────────────────────────────────────

@app.post("/api/generate", response_model=GenerateResponse)
async def generate_content(req: GenerateRequest):
    import urllib.request

    api_key = os.environ.get('GEMINI_API_KEY', '')
    if not api_key:
        from fastapi import HTTPException
        raise HTTPException(500, 'GEMINI_API_KEY not set')

    # URL の場合はテキスト取得
    source_text = req.source
    if req.source_type == 'url':
        if not _validate_url(req.source):
            from fastapi import HTTPException
            raise HTTPException(400, 'Invalid URL: https のみ、プライベートIPは不可')
        try:
            import html, re
            with urllib.request.urlopen(req.source, timeout=10) as r:
                raw = r.read().decode('utf-8', errors='replace')
                text = re.sub(r'<[^>]+>', ' ', raw)
                text = html.unescape(text)
                text = re.sub(r'\s+', ' ', text).strip()[:1500]
                source_text = text
        except Exception as e:
            _logger.warning("URL fetch failed, using raw source: %s", e)
            source_text = req.source

    # トーン別プロンプト生成
    tone_config = TONE_PROMPTS.get(req.tone, TONE_PROMPTS["professional"])
    if req.platform == "uword":
        platform_style = tone_config["uword_style"]
    elif req.platform == "umatching":
        platform_style = tone_config["umatching_style"]
    else:
        platform_style = tone_config.get("generic_style", tone_config["uword_style"])
    custom_addition = f"\n追加スタイル指示: {req.custom_style}" if req.custom_style else ""

    # プラットフォーム別プロンプト
    if req.platform == 'uword':
        prompt = f"""夜職・AIコンサル向けSNS投稿を作成してください。
参考情報: {source_text}
スタイル: {platform_style}{custom_addition}
要件: タイトル20〜40文字 / 本文150〜400文字
JSON形式: {{"title": "...", "content": "...", "hashtags": [...]}}"""

    elif req.platform == 'umatching':
        prompt = f"""ミニブログ投稿を作成してください。
参考情報: {source_text}
スタイル: {platform_style}{custom_addition}
要件: 本文150〜300文字 / ハッシュタグ3〜5個
JSON形式: {{"title": "", "content": "...", "hashtags": [...]}}"""

    elif req.platform == 'facebook':
        prompt = f"""Facebook投稿を作成してください。
参考情報: {source_text}
スタイル: {platform_style}{custom_addition}
要件: 本文200〜800文字 / ストーリーテリング形式 / 適度な改行 / 絵文字1〜3個 / ハッシュタグ2〜5個 / 最後にコメント誘導CTAを入れる
JSON形式: {{"title": "", "content": "...", "hashtags": [...]}}"""

    elif req.platform == 'instagram':
        prompt = f"""Instagram投稿のキャプションを作成してください。
参考情報: {source_text}
スタイル: {platform_style}{custom_addition}
要件: 最初の1〜2行で強いフック / 本文100〜300文字 / 改行・空行を多用して読みやすく / 絵文字10〜20個 / ハッシュタグ15〜30個（本文末尾にまとめて記載）
JSON形式: {{"title": "", "content": "...", "hashtags": [...]}}"""

    elif req.platform == 'x_twitter':
        prompt = f"""X（Twitter）の投稿を作成してください。
参考情報: {source_text}
スタイル: {platform_style}{custom_addition}
要件: 【最重要】本文は日本語で140文字以内に収める / 最初の一文で強いフック / シンプルで力強い / ハッシュタグは0〜2個のみ
JSON形式: {{"title": "", "content": "...", "hashtags": [...]}}"""

    elif req.platform == 'note':
        cta_addition = ""
        cta_requirement = "自然な行動喚起を100字程度で入れる"
        if req.cta_url or req.cta_text:
            cta_addition = f"\nCTA指定: この内容をさらに深く、あなたのビジネスに個別最適化して実装したい方は→ {req.cta_url}"
            cta_requirement = f"自然な行動喚起として次の文を必ず含める: 「この内容をさらに深く、あなたのビジネスに個別最適化して実装したい方は→ {req.cta_url}」"
        prompt = f"""Note向けの有料級プレミアム記事を作成してください。
参考情報: {source_text}
スタイル: {platform_style}{custom_addition}{cta_addition}

出力条件:
- 本文は必ず5000字以上
- タイトルは25〜40字で、数字と読者ベネフィットを含める
- 具体的な数字、事例、Before/After、実績を入れて信頼性を作る
- 専門用語は使ってよいが、初出時に短く説明する
- 「これ無料でいいの？」「スクショして保存したい」と感じる密度にする
- Markdown記法を使い、読みやすい見出しと箇条書きを適度に入れる

記事構成:
1. 冒頭フック（200字）: 読者の痛み・欲求に刺さる「あなたにとって○○ですか？」形式
2. 問題提起（300字）: なぜ多くの人が失敗するのか
3. 著者の体験/実績（400字）: 具体的な数字・成果・ケースで信頼を作る
4. 核心コンテンツ（2000字以上）: ステップバイステップの実践メソッド
5. 読者への問いかけ（200字）: 行動につながる気づきを促す
6. CTA（100字）: {cta_requirement}

JSON形式のみで返してください:
{{"title": "25-40字タイトル with numbers+benefit", "content": "5000字+本文", "hashtags": ["tag1","tag2","tag3"]}}"""

        def _call_note_gemini() -> dict:
            url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}'
            body = json.dumps({
                'contents': [{'parts': [{'text': prompt}]}],
                'generationConfig': {
                    'maxOutputTokens': 8192,
                    'responseMimeType': 'application/json',
                },
            }).encode('utf-8')
            request = urllib.request.Request(
                url,
                data=body,
                headers={'Content-Type': 'application/json'},
                method='POST',
            )
            with urllib.request.urlopen(request, timeout=60) as response:
                resp = json.loads(response.read())
            text = resp['candidates'][0]['content']['parts'][0]['text']
            parsed = json.loads(text)
            if isinstance(parsed, list):
                parsed = parsed[0] if parsed else {}
            return parsed

        try:
            loop = asyncio.get_running_loop()
            parsed = await loop.run_in_executor(None, _call_note_gemini)
            return GenerateResponse(
                title=parsed.get('title', ''),
                content=parsed.get('content', ''),
                hashtags=parsed.get('hashtags', [])
            )
        except Exception as e:
            return GenerateResponse(title="", content=f"生成エラー: {e}", hashtags=[])

    elif req.platform == 'linkedin':
        prompt = f"""LinkedIn投稿を作成してください。
参考情報: {source_text}
スタイル: {platform_style}{custom_addition}
要件: フック1行（改行後に本文）/ ビジネス知見・学びを中心に300〜800文字 / 箇条書き活用 / ハッシュタグ3〜5個 / 最後にコメント誘導
JSON形式: {{"title": "", "content": "...", "hashtags": [...]}}"""

    else:
        prompt = f"""SNS投稿を作成してください。
参考情報: {source_text}
スタイル: {platform_style}{custom_addition}
要件: 本文150〜400文字 / ハッシュタグ3〜5個
JSON形式: {{"title": "", "content": "...", "hashtags": [...]}}"""

    parsed = await _call_gemini(prompt)

    return GenerateResponse(
        title=parsed.get('title', ''),
        content=parsed.get('content', ''),
        hashtags=parsed.get('hashtags', [])
    )


@app.post('/api/derive-from-note', response_model=DeriveResponse)
async def derive_from_note(req: DeriveRequest):
    api_key = os.environ.get('GEMINI_API_KEY', '')
    if not api_key:
        return DeriveResponse(results=[])

    PLATFORM_LIMITS = {
        'x_twitter': 280, 'threads': 500, 'instagram': 2200,
        'facebook': 2000, 'linkedin': 3000, 'uword': 400, 'umatching': 300,
    }
    PLATFORM_NAMES = {
        'x_twitter': 'X(Twitter)', 'threads': 'Threads',
        'instagram': 'Instagram', 'facebook': 'Facebook',
        'linkedin': 'LinkedIn', 'uword': 'Uワード速報', 'umatching': 'ミニブログ',
    }
    if req.note_url:
        cta_instruction = f"\n\n各SNS投稿の末尾に「詳しくはこちら → {req.note_url}」を自然な形で含めること。"
    elif req.cta_url:
        cta_instruction = f"\n\n各SNS投稿の末尾に「{req.cta_text or '詳しくはこちら'} → {req.cta_url}」を自然な形で含めること。"
    else:
        cta_instruction = ""

    prompt = f'''以下のNote記事を、各SNSの文字数・トーンに最適化して派生投稿を生成してください。

=== Note元記事 ===
タイトル: {req.note_title or '（なし）'}
{req.note_content[:3000]}
=== ここまで ===

以下の各プラットフォーム用に最適化した投稿をJSON配列で返してください:
{json.dumps([{"platform": p, "char_limit": PLATFORM_LIMITS.get(p, 500), "name": PLATFORM_NAMES.get(p, p)} for p in req.platforms], ensure_ascii=False)}

各プラットフォームの要件:
- x_twitter: 280字以内、インパクト重視、ハッシュタグ2〜3個
- threads: 500字以内、会話的でカジュアル
- instagram: キャプション形式、絵文字あり、ハッシュタグ5〜10個
- facebook: 2000字以内、読みやすく共感を誘う
- linkedin: ビジネス向け、学びや洞察を強調、3000字以内
- uword: 400字以内、個人事業主・経営者向け硬派トーン
- umatching: 300字以内、女性向けフレンドリー

出力フォーマット（JSONのみ）:
[
  {{"platform": "x_twitter", "title": "", "content": "...", "hashtags": ["tag1", "tag2"]}},
  {{"platform": "threads", "title": "", "content": "...", "hashtags": []}},
  ...
]''' + cta_instruction

    try:
        import urllib.request as _urlreq
        url = (f'https://generativelanguage.googleapis.com/v1beta/models/'
               f'gemini-2.0-flash:generateContent?key={api_key}')
        body = json.dumps({
            'contents': [{'parts': [{'text': prompt}]}],
            'generationConfig': {'responseMimeType': 'application/json'}
        }).encode('utf-8')
        http_req = _urlreq.Request(url, data=body,
                                   headers={'Content-Type': 'application/json'}, method='POST')
        loop = asyncio.get_event_loop()
        def _fetch():
            with _urlreq.urlopen(http_req, timeout=60) as r:
                return json.loads(r.read())
        resp = await loop.run_in_executor(None, _fetch)
        text = resp['candidates'][0]['content']['parts'][0]['text']
        items = json.loads(text)
        if not isinstance(items, list):
            items = []
        results = [DeriveResult(**item) for item in items if isinstance(item, dict)]
        return DeriveResponse(results=results)
    except Exception as e:
        _logger.warning('derive_from_note error: %s', e)
        return DeriveResponse(results=[])


@app.get("/api/tones")
async def get_tones():
    return [{"value": k, "label": v["label"]} for k, v in TONE_PROMPTS.items()]


@app.get("/api/platforms")
async def get_platforms():
    return [{"value": k, **v} for k, v in PLATFORM_CONFIGS.items()]


# ──────────────────────────────────────────────────────────
# URL / 動画 要約エンドポイント
# ──────────────────────────────────────────────────────────

@app.post("/api/summarize", response_model=SummarizeResponse)
async def summarize_url_endpoint(req: SummarizeRequest):
    """記事URLまたはYouTube URLを要約する。YouTube はGemini動画理解を使用。"""
    import urllib.request as _req_lib
    import html as _html_lib
    import re as _re_lib

    if not _validate_url(req.url):
        from fastapi import HTTPException
        raise HTTPException(400, 'Invalid URL: https のみ、プライベートIPは不可')

    api_key = os.environ.get('GEMINI_API_KEY', '')
    if not api_key:
        from fastapi import HTTPException
        raise HTTPException(500, 'GEMINI_API_KEY not set')

    if _is_youtube_url(req.url):
        # YouTube: Gemini の動画理解機能でダイレクト処理
        gemini_url = (
            f'https://generativelanguage.googleapis.com/v1beta/models/'
            f'gemini-2.0-flash:generateContent?key={api_key}'
        )
        body = json.dumps({
            'contents': [{
                'parts': [
                    {'file_data': {'mime_type': 'video/youtube', 'file_uri': req.url}},
                    {'text': (
                        '動画の内容を日本語で要約してください。\n'
                        '・主要なテーマとキーメッセージ\n'
                        '・視聴者が得られる価値\n'
                        '・具体的なポイント3〜5点\n'
                        '動画タイトル（推定）と本文要約をまとめてください。'
                        'JSON形式: {"title": "...", "summary": "..."}'
                    )},
                ]
            }],
            'generationConfig': {'responseMimeType': 'application/json'},
        }).encode('utf-8')
        try:
            request = _req_lib.Request(
                gemini_url, data=body,
                headers={'Content-Type': 'application/json'}, method='POST'
            )
            with _req_lib.urlopen(request, timeout=60) as r:
                resp = json.loads(r.read())
            text = resp['candidates'][0]['content']['parts'][0]['text']
            parsed = json.loads(text)
            if isinstance(parsed, list):
                parsed = parsed[0] if parsed else {}
            return SummarizeResponse(
                title=parsed.get('title', 'YouTube動画'),
                summary=parsed.get('summary', text),
                source_type='youtube',
            )
        except Exception as e:
            _logger.warning("YouTube summarize failed: %s", e)
            from fastapi import HTTPException
            raise HTTPException(500, f'YouTube要約失敗: {e}')

    else:
        # 記事: HTML取得 → テキスト抽出 → Gemini で要約
        try:
            with _req_lib.urlopen(req.url, timeout=15) as r:
                raw = r.read().decode('utf-8', errors='replace')
        except Exception as e:
            from fastapi import HTTPException
            raise HTTPException(502, f'URL取得失敗: {e}')

        title_match = _re_lib.search(r'<title[^>]*>([^<]+)</title>', raw, _re_lib.IGNORECASE)
        page_title = _html_lib.unescape(title_match.group(1)).strip() if title_match else ''

        text = _re_lib.sub(r'<[^>]+>', ' ', raw)
        text = _html_lib.unescape(text)
        text = _re_lib.sub(r'\s+', ' ', text).strip()[:4000]

        prompt = (
            f'以下の記事テキストを日本語で要約してください。\n'
            f'記事テキスト: {text}\n\n'
            f'要約ルール:\n'
            f'・3〜5段落でまとめる\n'
            f'・主要ポイントと読者が得られる価値を含める\n'
            f'・元の記事タイトル（推定）も含める\n'
            f'JSON形式: {{"title": "...", "summary": "..."}}'
        )
        try:
            parsed = await _call_gemini(prompt)
            return SummarizeResponse(
                title=parsed.get('title', page_title),
                summary=parsed.get('summary', text[:500]),
                source_type='article',
            )
        except Exception as e:
            _logger.warning("Article summarize failed: %s", e)
            from fastapi import HTTPException
            raise HTTPException(500, f'記事要約失敗: {e}')


# ──────────────────────────────────────────────────────────
# Gemini 画像生成エンドポイント
# ──────────────────────────────────────────────────────────

@app.post("/api/generate-image", response_model=ImageGenResponse)
async def generate_image_endpoint(req: ImageGenRequest):
    """投稿内容からGeminiで画像を生成する。プロンプト未指定時は自動生成。"""
    import urllib.request as _req_lib

    api_key = os.environ.get('GEMINI_API_KEY', '')
    if not api_key:
        from fastapi import HTTPException
        raise HTTPException(500, 'GEMINI_API_KEY not set')

    # Step 1: 画像プロンプト決定
    if req.custom_prompt.strip():
        image_prompt = req.custom_prompt.strip()
    else:
        # 投稿テキストから英語の画像プロンプトを自動生成
        auto_prompt_req = (
            f'以下のSNS投稿に最も合う画像を、英語で1〜2文の画像生成プロンプトとして記述してください。\n'
            f'プラットフォーム: {req.platform}\n'
            f'投稿内容: {req.content[:600]}\n\n'
            f'JSON形式: {{"prompt": "..."}}'
        )
        try:
            result = await _call_gemini(auto_prompt_req)
            image_prompt = result.get('prompt', 'A professional high-quality photo for a social media post')
        except Exception:
            image_prompt = 'A professional high-quality photo for a social media post'

    # Step 2: プラットフォーム別スタイル付加
    _platform_style = {
        'instagram': ', vibrant lifestyle photography, square format, Instagram aesthetic',
        'facebook':  ', warm engaging tones, horizontal format, professional photography',
        'note':      ', clean minimal blog header, white background, professional',
        'x_twitter': ', bold eye-catching, high contrast, impactful',
        'linkedin':  ', professional business photography, clean neutral background',
        'uword':     ', professional high quality',
        'umatching': ', appealing photogenic lifestyle',
    }
    full_prompt = image_prompt + _platform_style.get(req.platform, '')

    # Step 3: Imagen 4 Fast で画像生成
    gemini_url = (
        f'https://generativelanguage.googleapis.com/v1beta/models/'
        f'imagen-4.0-fast-generate-001:predict?key={api_key}'
    )
    body = json.dumps({
        'instances': [{'prompt': full_prompt}],
        'parameters': {'sampleCount': 1},
    }).encode('utf-8')

    request = _req_lib.Request(
        gemini_url, data=body,
        headers={'Content-Type': 'application/json'}, method='POST'
    )
    try:
        with _req_lib.urlopen(request, timeout=90) as r:
            resp = json.loads(r.read())
        predictions = resp.get('predictions', [])
        if not predictions:
            from fastapi import HTTPException
            raise HTTPException(500, '画像データが含まれていません')
        pred = predictions[0]
        return ImageGenResponse(
            image_data=pred['bytesBase64Encoded'],
            mime_type=pred.get('mimeType', 'image/png'),
            used_prompt=full_prompt,
        )
    except Exception as e:
        _logger.warning("Image generation failed: %s", e)
        from fastapi import HTTPException
        raise HTTPException(500, f'画像生成失敗: {e}')


# ──────────────────────────────────────────────────────────
# 定型文 CRUD
# ──────────────────────────────────────────────────────────

@app.get("/api/boilerplate", response_model=Boilerplate)
async def get_boilerplate():
    return _load_boilerplate()


@app.put("/api/boilerplate")
async def save_boilerplate(bp: Boilerplate):
    BOILERPLATE_PATH.write_text(json.dumps(bp.dict(), ensure_ascii=False, indent=2))
    return {"ok": True}


# ──────────────────────────────────────────────────────────
# ログ
# ──────────────────────────────────────────────────────────

@app.get("/api/logs")
async def get_logs(limit: int = Query(default=20, le=200)):
    db_path = AP_BACKEND / "data" / "autopost.db"
    with sqlite3.connect(str(db_path)) as conn:
        rows = conn.execute(
            "SELECT platform, status, title, substr(content,1,60), posted_at, error_message "
            "FROM autopost_logs ORDER BY posted_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
    return [
        {
            "platform": r[0],
            "status": r[1],
            "title": r[2],
            "content": r[3],
            "posted_at": r[4],
            "error": r[5],
        }
        for r in rows
    ]


def _merge_boilerplate_with_creds(content: str, platform: str, hashtags_str: str, creds: dict) -> dict:
    """リトライ・修復用: _merge_boilerplate を呼び出して content と creds を dict で返す"""
    merged_content, merged_hashtags = _merge_boilerplate(platform, content, [], hashtags_str)
    if merged_hashtags:
        creds["hashtags"] = merged_hashtags
    return {"content": merged_content, "creds": creds}


def _get_creds_for_platform(platform: str):
    """DB から有効なクレデンシャルを取得して復号する。見つからなければ None を返す。"""
    from services.poster.encryption import decrypt_credentials

    db_path = AP_BACKEND / "data" / "autopost.db"
    with sqlite3.connect(str(db_path)) as conn:
        row = conn.execute(
            "SELECT credentials FROM autopost_configs WHERE platform=? AND is_active=1 LIMIT 1",
            (platform,)
        ).fetchone()
    if not row:
        return None
    return decrypt_credentials(row[0])


# ──────────────────────────────────────────────────────────
# リトライエンドポイント
# ──────────────────────────────────────────────────────────

@app.post("/api/retry")
async def retry_post():
    """最後の失敗投稿を同じパラメータで再試行"""
    if not _last_post:
        return {"success": False, "error": "リトライ対象がありません"}

    platform = _last_post.get("platform", "uword")
    title = _last_post.get("title", "")
    content = _last_post.get("content", "")
    hashtags = _last_post.get("hashtags_str", "")

    # 前回投稿時のクレデンシャルを優先、なければ DB フォールバック
    creds = _last_post.get("creds") or _get_creds_for_platform(platform)
    if creds is None:
        return {"success": False, "error": f"{platform} の設定が見つかりません。クレデンシャルを入力してください。"}

    merged = _merge_boilerplate_with_creds(content, platform, hashtags, creds)

    if platform == "uword":
        from services.poster.platforms.uword import UwordPlatform
        result = await UwordPlatform().post(
            title=title or None,
            content=merged["content"],
            credentials=merged["creds"],
        )
    elif platform == "umatching":
        from services.poster.platforms.umatching import UmatchingPlatform
        result = await UmatchingPlatform().post(
            title=None,
            content=merged["content"],
            credentials=merged["creds"],
        )
    else:
        return {"success": False, "error": "unknown platform"}

    return {"success": result.success, "post_url": result.post_url or "", "error": result.error or ""}


# ──────────────────────────────────────────────────────────
# Playwright 修復エンドポイント
# ──────────────────────────────────────────────────────────

@app.post("/api/repair")
async def repair_posting():
    """Playwright で投稿フォームを診断・修復して再投稿を試みる。ログを返す。"""
    if not _last_post:
        return {"success": False, "logs": ["修復対象がありません"], "error": ""}

    logs = []
    platform = _last_post.get("platform", "uword")
    content = _last_post.get("content", "")
    title = _last_post.get("title", "")
    hashtags = _last_post.get("hashtags_str", "")

    import datetime

    creds = _get_creds_for_platform(platform)
    if creds is None:
        return {"success": False, "logs": [f"{platform} の設定が見つかりません"], "error": ""}

    merged = _merge_boilerplate_with_creds(content, platform, hashtags, creds)
    final_content = merged["content"]
    final_creds = merged["creds"]

    logs.append(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 修復開始: platform={platform}")

    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)

            if platform == "uword":
                page = await browser.new_page()
                logs.append(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] ログインページへ移動")
                await page.goto(final_creds['site_url'], wait_until='networkidle')

                login_input = page.locator('#ion-input-0')
                if await login_input.count() > 0:
                    await login_input.fill(final_creds['username'])
                    await page.locator('#ion-input-1').fill(final_creds['password'])
                    await page.locator('.submit_btn button').click()
                    await page.wait_for_load_state('networkidle')
                    logs.append(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] ログイン完了: {page.url}")

                await page.goto(final_creds['post_url'], wait_until='networkidle')
                logs.append(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 投稿ページ: {page.url}")

                if 'realTimeEdit' in page.url:
                    await browser.close()
                    return {"success": False, "logs": logs + ["日次投稿制限に達しています"], "error": "DAILY_LIMIT"}

                # フォーム診断
                diagnosis = await page.evaluate("""() => {
                    const form = document.querySelector('form.realTimePostForm');
                    if (!form) return {found: false};
                    const controls = Array.from(form.querySelectorAll('input, textarea, ion-input')).map(el => ({
                        tag: el.tagName, name: el.name, ngInvalid: el.classList.contains('ng-invalid')
                    }));
                    return {found: true, formClass: form.className, controls};
                }""")
                logs.append(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] フォーム診断: {diagnosis}")

                if not diagnosis.get('found'):
                    await browser.close()
                    return {"success": False, "logs": logs + ["フォームが見つかりません"], "error": "FORM_NOT_FOUND"}

                # タイトル入力
                import datetime as _dt
                fill_title = (title or f"今日のAI活用術（{_dt.date.today().strftime('%m/%d')}）")[:50]
                await page.evaluate("""([sel, text]) => {
                    const el = document.querySelector(sel);
                    if (!el) return;
                    el.value = text;
                    el.dispatchEvent(new CustomEvent('ionInput', {detail:{value:text}, bubbles:true}));
                    el.dispatchEvent(new CustomEvent('ionChange', {detail:{value:text}, bubbles:true}));
                    const native = el.querySelector('input') || el.shadowRoot?.querySelector('input');
                    if (native) {
                        const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set;
                        if (setter) setter.call(native, text);
                        native.dispatchEvent(new Event('input', {bubbles:true}));
                        native.dispatchEvent(new Event('change', {bubbles:true}));
                    }
                }""", ['ion-input[name="title"]', fill_title])
                await page.wait_for_timeout(400)

                # 本文入力
                await page.evaluate("""([sel, text]) => {
                    const el = document.querySelector(sel);
                    if (!el) return;
                    const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value')?.set;
                    if (setter) setter.call(el, text);
                    el.dispatchEvent(new Event('focus', {bubbles:true}));
                    el.dispatchEvent(new Event('input', {bubbles:true}));
                    el.dispatchEvent(new Event('change', {bubbles:true}));
                    el.dispatchEvent(new Event('blur', {bubbles:true}));
                }""", ['textarea[name="content"]', final_content])
                await page.wait_for_timeout(500)

                # カテゴリ選択
                for cat_sel in ['label[for="radio_category_3"]', 'label[for="radio_category_2"]']:
                    lbl = page.locator(cat_sel)
                    if await lbl.count() > 0:
                        await lbl.first.click()
                        logs.append(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] カテゴリ選択: {cat_sel}")
                        break
                await page.wait_for_timeout(1500)

                # ボタン状態確認
                submit = page.locator('ion-button:has-text("投稿"), button:has-text("投稿")')
                is_disabled = await submit.first.evaluate("el => el.disabled || el.classList.contains('button-disabled')")
                logs.append(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] ボタン disabled: {is_disabled}")

                if is_disabled:
                    re_diag = await page.evaluate("""() => {
                        const form = document.querySelector('form.realTimePostForm');
                        return form ? form.className : 'not found';
                    }""")
                    logs.append(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 再診断: {re_diag}")
                    await browser.close()
                    return {"success": False, "logs": logs + ["フォームバリデーション失敗 — DOM変更の可能性があります"], "error": "FORM_INVALID"}

                await submit.first.evaluate("el => el.click()")
                await page.wait_for_load_state('networkidle')
                await page.wait_for_timeout(2000)
                final_url = page.url
                logs.append(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 投稿後URL: {final_url}")
                await browser.close()
                return {"success": True, "logs": logs + ["修復投稿成功"], "post_url": final_url}

            elif platform == "umatching":
                SESSION_PATH = Path('/tmp/umatching-session.json')

                if SESSION_PATH.exists():
                    context = await browser.new_context(
                        storage_state=str(SESSION_PATH),
                        viewport={"width": 1280, "height": 800}
                    )
                else:
                    context = await browser.new_context(viewport={"width": 1280, "height": 800})

                page = await context.new_page()
                logs.append(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] ミニブログ編集ページへ移動")
                await page.goto('https://uword-matching.com/um/miniblog/edit/index.html', wait_until='networkidle')

                if 'home' in page.url:
                    logs.append(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] セッション切れ — Cognito再ログイン試行")
                    if final_creds.get('username') and final_creds.get('password'):
                        await page.goto('https://uword-matching.com/um/oauth/densan/login/', wait_until='networkidle')
                        await page.wait_for_selector('#signInFormUsername', state='visible', timeout=10000)
                        await page.locator('#signInFormUsername').fill(final_creds['username'])
                        await page.locator('#signInFormPassword').fill(final_creds['password'])
                        await page.locator('input[name="signInSubmitButton"]').click()
                        await page.wait_for_load_state('networkidle')
                        await page.goto('https://uword-matching.com/um/miniblog/edit/index.html', wait_until='networkidle')
                        logs.append(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 再ログイン後URL: {page.url}")

                try:
                    await page.wait_for_selector('#introduction', state='visible', timeout=10000)
                except Exception as e:
                    _logger.warning("repair: #introduction not found: %s", e)
                    await browser.close()
                    return {"success": False, "logs": logs + ["フォーム未検出"], "error": "FORM_NOT_FOUND"}

                await page.locator('#introduction').fill(final_content)
                logs.append(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 本文入力完了")

                await page.get_by_text('投稿する').click()
                await page.wait_for_load_state('networkidle')
                await page.wait_for_timeout(2000)

                # セッション保存
                try:
                    state = await context.storage_state()
                    SESSION_PATH.write_text(json.dumps(state))
                except Exception as e:
                    _logger.warning("repair: session save failed: %s", e)

                final_url = page.url
                logs.append(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 投稿後URL: {final_url}")
                await browser.close()

                if '/um/miniblog' in final_url:
                    return {"success": True, "logs": logs + ["修復投稿成功"], "post_url": final_url}
                else:
                    return {"success": False, "logs": logs + ["予期しないURLへ遷移"], "error": "UNEXPECTED_URL"}

            else:
                await browser.close()
                return {"success": False, "logs": logs + ["unknown platform"], "error": "unknown platform"}

    except Exception as e:
        return {"success": False, "logs": logs + [f"例外: {str(e)}"], "error": str(e)}


# ──────────────────────────────────────────────────────────
# 自己修復投稿エンドポイント
# ──────────────────────────────────────────────────────────

@app.post("/api/post-with-healing")
async def post_with_healing_endpoint(
    platform: str = Form(...),
    title: str = Form(""),
    content: str = Form(...),
    hashtags: str = Form(""),
    cred_username: str = Form(""),
    cred_password: str = Form(""),
    cred_site_url: str = Form(""),
    cred_post_url: str = Form(""),
    image: UploadFile = File(None)
):
    """自己修復投稿: 失敗時に自動診断・修復・再投稿"""
    from self_healing import heal_and_post

    # ユーザー入力が優先、未入力なら DB フォールバック
    if cred_username and cred_password and cred_site_url:
        creds = {
            "username": cred_username,
            "password": cred_password,
            "site_url": cred_site_url,
            "post_url": cred_post_url or cred_site_url,
        }
    else:
        from services.poster.encryption import decrypt_credentials

        db_path = AP_BACKEND / 'data' / 'autopost.db'
        with sqlite3.connect(str(db_path)) as conn:
            row = conn.execute(
                "SELECT credentials FROM autopost_configs WHERE platform=? AND is_active=1 LIMIT 1",
                (platform,)
            ).fetchone()
        if not row:
            return {"success": False, "error": f"{platform} の設定が見つかりません。クレデンシャルを入力してください。", "healing_log": []}
        creds = decrypt_credentials(row[0])

    hashtag_list = [h.strip() for h in hashtags.split(',') if h.strip()]

    # 定型文マージ
    merged_content, merged_hashtags = _merge_boilerplate(platform, content, hashtag_list)
    if merged_hashtags:
        creds["hashtags"] = merged_hashtags

    # 最後の投稿パラメータを記憶（リトライ・修復用）
    _last_post.update({
        "platform": platform,
        "title": title,
        "content": merged_content,
        "hashtags_str": hashtags,
        "creds": creds,
    })

    # 画像処理
    image_path = None
    tmp = None
    if image and image.filename:
        suffix = Path(image.filename).suffix.lower()
        if suffix in _ALLOWED_IMAGE_SUFFIXES:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            shutil.copyfileobj(image.file, tmp)
            tmp.close()
            image_path = tmp.name

    try:
        result = await heal_and_post(
            platform=platform,
            content=merged_content,
            title=title,
            credentials=creds,
        )
        return {
            "success": result.success,
            "post_url": result.post_url,
            "error": result.error,
            "healing_log": result.healing_log,
        }
    finally:
        if tmp:
            os.unlink(tmp.name)


# ──────────────────────────────────────────────────────────
# 週次レビュー
# ──────────────────────────────────────────────────────────

def _parse_review_md(md: str, date: str) -> dict:
    lines = md.splitlines()
    summary = {"total": 0, "avg_score": 0.0, "high_score": 0, "needs_improvement": 0}
    for line in lines:
        if "投稿数（成功）" in line:
            m = _re.search(r"(\d+)", line)
            if m:
                summary["total"] = int(m.group(1))
        elif "平均スコア" in line:
            m = _re.search(r"([\d.]+)", line)
            if m:
                summary["avg_score"] = float(m.group(1))
        elif "高評価" in line:
            m = _re.search(r"高評価.*?(\d+)件", line)
            if m:
                summary["high_score"] = int(m.group(1))
            m2 = _re.search(r"要改善.*?(\d+)件", line)
            if m2:
                summary["needs_improvement"] = int(m2.group(1))
    posts = []
    cur = None
    for line in lines:
        m = _re.match(r"### \[(.+?)\] (.+?) — スコア: (.+?)$", line)
        if m:
            if cur:
                posts.append(cur)
            sm = _re.search(r"(\d+)", m.group(3))
            cur = {
                "platform": m.group(1), "title": m.group(2),
                "score": int(sm.group(1)) if sm else None,
                "posted_at": "", "content": "", "hook_strength": "",
                "cta_present": False, "target_match": "", "forbidden_words": "", "improvement": ""
            }
        elif cur:
            if line.startswith("**投稿日時:**"):
                cur["posted_at"] = line.replace("**投稿日時:**", "").strip()
            elif line.startswith("**本文:**"):
                cur["content"] = line.replace("**本文:**", "").strip()
            elif line.startswith("- フック:"):
                cur["hook_strength"] = line.replace("- フック:", "").strip()
            elif line.startswith("- CTA:"):
                cur["cta_present"] = "あり" in line
            elif line.startswith("- ターゲット一致:"):
                cur["target_match"] = line.replace("- ターゲット一致:", "").strip()
            elif line.startswith("- 禁止語:"):
                cur["forbidden_words"] = line.replace("- 禁止語:", "").strip()
            elif line.startswith("- 改善提案:"):
                cur["improvement"] = line.replace("- 改善提案:", "").strip()
    if cur:
        posts.append(cur)
    return {"summary": summary, "posts": posts, "date": date}


@app.get("/api/review/latest")
async def get_latest_review():
    """最新週次レビューをJSON形式で返す"""
    if not REPORTS_DIR.exists():
        return {"summary": {}, "posts": [], "date": ""}
    files = sorted(REPORTS_DIR.glob("*.md"), reverse=True)
    if not files:
        return {"summary": {}, "posts": [], "date": ""}
    return _parse_review_md(files[0].read_text(encoding="utf-8"), files[0].stem)


@app.post("/api/review/run")
async def run_weekly_review(dry_run: bool = False):
    """週次レビュースクリプトを実行"""
    import asyncio
    script = AP_BACKEND / 'scripts' / 'weekly_review.py'
    cmd = [sys.executable, str(script)]
    if dry_run:
        cmd.append("--dry-run")
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=str(AP_BACKEND),
    )
    stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=120)
    return {"returncode": proc.returncode, "output": stdout.decode("utf-8", errors="replace")[-3000:]}


# ──────────────────────────────────────────────────────────
# Playwright 診断エンドポイント
# ──────────────────────────────────────────────────────────

@app.get("/api/diagnose/{platform}")
async def diagnose_platform(platform: str):
    """Playwright でプラットフォームのページ状態を診断"""
    if platform not in {"uword", "umatching"}:
        return {"ok": False, "error": f"Unsupported platform: {platform}", "checks": []}
    import datetime
    from services.poster.encryption import decrypt_credentials
    from playwright.async_api import async_playwright

    db_path = AP_BACKEND / 'data' / 'autopost.db'
    with sqlite3.connect(str(db_path)) as conn:
        row = conn.execute(
            "SELECT credentials FROM autopost_configs WHERE platform=? AND is_active=1 LIMIT 1",
            (platform,)
        ).fetchone()
    if not row:
        return {"ok": False, "error": f"{platform} の設定なし", "checks": []}

    creds = decrypt_credentials(row[0])
    checks = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            if platform == "uword":
                page = await browser.new_page()
                checks.append({"label": "ログインページ", "status": "checking", "detail": ""})
                await page.goto(creds['site_url'], wait_until='networkidle', timeout=20000)
                SEL_USER = 'input[name="ion-input-0"], input[name="username"], input[type="text"][name*="user"]'
                SEL_PASS = 'input[name="ion-input-1"], input[name="password"], input[type="password"]'
                SEL_SUBMIT = '.submit_btn button, .login_container button'
                login_found = await page.locator(SEL_USER).count() > 0
                checks[-1]["status"] = "ok" if login_found else "warn"
                checks[-1]["detail"] = f"URL: {page.url}, ログインフォーム: {'あり' if login_found else 'なし'}"

                if login_found:
                    await page.wait_for_selector(SEL_USER, state='visible', timeout=10000)
                    await page.locator(SEL_USER).first.fill(creds['username'])
                    await page.locator(SEL_PASS).first.fill(creds['password'])
                    await page.locator(SEL_SUBMIT).first.click()
                    await page.wait_for_load_state('networkidle')
                    try:
                        await page.wait_for_function(
                            "() => !window.location.href.toLowerCase().includes('login')",
                            timeout=8000,
                        )
                    except Exception:
                        pass
                    logged_in = 'login' not in page.url
                    checks.append({"label": "ログイン", "status": "ok" if logged_in else "error",
                                   "detail": f"URL: {page.url}"})

                    if logged_in:
                        await page.goto(creds['post_url'], wait_until='networkidle', timeout=20000)
                        daily_limit = 'realTimeEdit' in page.url
                        form_found = await page.locator('textarea[name="content"]').count() > 0
                        checks.append({"label": "投稿ページ",
                                       "status": "warn" if daily_limit else ("ok" if form_found else "error"),
                                       "detail": f"URL: {page.url}, 日次制限: {daily_limit}, フォーム: {form_found}"})

                        if form_found:
                            form_state = await page.evaluate("""() => {
                                const form = document.querySelector('form.realTimePostForm');
                                return form ? form.className : 'not found';
                            }""")
                            checks.append({"label": "Angularフォーム状態", "status": "ok", "detail": form_state})

            elif platform == "umatching":
                SESSION_PATH = Path('/tmp/umatching-session.json')
                if SESSION_PATH.exists():
                    context = await browser.new_context(storage_state=str(SESSION_PATH))
                else:
                    context = await browser.new_context()
                    checks.append({"label": "セッション", "status": "warn",
                                   "detail": "storage_state なし — 再ログイン必要"})

                page = await context.new_page()
                await page.goto('https://uword-matching.com/um/miniblog/', wait_until='networkidle', timeout=20000)
                session_ok = '/um/miniblog' in page.url
                checks.append({"label": "セッション有効性", "status": "ok" if session_ok else "error",
                               "detail": f"URL: {page.url}"})

                if session_ok:
                    await page.goto('https://uword-matching.com/um/miniblog/edit/index.html',
                                    wait_until='networkidle')
                    await page.wait_for_timeout(2000)
                    form_found = await page.locator('#introduction').count() > 0
                    checks.append({"label": "投稿フォーム", "status": "ok" if form_found else "error",
                                   "detail": f"URL: {page.url}, #introduction: {form_found}"})
        finally:
            await browser.close()

    all_ok = all(c["status"] in ("ok", "warn") for c in checks)
    return {"ok": all_ok, "platform": platform, "checks": checks,
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}


# ──────────────────────────────────────────────────────────
# ログ詳細エンドポイント
# ──────────────────────────────────────────────────────────

@app.get("/api/logs/detail")
async def get_logs_detail(limit: int = Query(default=50, le=500)):
    """エラーメッセージ込みの詳細ログ"""
    db_path = AP_BACKEND / 'data' / 'autopost.db'
    with sqlite3.connect(str(db_path)) as conn:
        rows = conn.execute(
            "SELECT id, platform, status, title, content, posted_at, error_message, retry_attempt "
            "FROM autopost_logs ORDER BY posted_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
    return [
        {
            "id": r[0], "platform": r[1], "status": r[2], "title": r[3],
            "content": r[4][:200] if r[4] else "", "posted_at": r[5],
            "error": r[6], "retry_attempt": r[7]
        }
        for r in rows
    ]


# ──────────────────────────────────────────────────────────
# トレンドリサーチエンドポイント
# ──────────────────────────────────────────────────────────

@app.get("/api/trending")
async def get_trending():
    """Google Trends JP + Yahoo Japan ニュース RSS からトレンド取得"""
    import asyncio
    import feedparser
    import datetime as _dt

    feeds = [
        ("google_trends", "https://trends.google.co.jp/trending/rss?geo=JP"),
        ("yahoo_news",    "https://news.yahoo.co.jp/rss/topics/top-picks.xml"),
    ]

    results = []
    for source, url in feeds:
        try:
            import socket as _socket
            def _parse_with_timeout(u):
                old = _socket.getdefaulttimeout()
                _socket.setdefaulttimeout(10)
                try:
                    return feedparser.parse(u)
                finally:
                    _socket.setdefaulttimeout(old)
            loop = asyncio.get_event_loop()
            feed = await loop.run_in_executor(None, _parse_with_timeout, url)
            for entry in feed.entries[:8]:
                results.append({
                    "source": source,
                    "title": entry.get("title", ""),
                    "link":  entry.get("link", ""),
                    "published": entry.get("published", ""),
                    "summary": entry.get("summary", "")[:200],
                })
        except Exception as e:
            _logger.warning("Trending feed error %s: %s", source, e)

    return {"items": results, "fetched_at": _dt.datetime.now().isoformat()}


class ArticleSearchRequest(BaseModel):
    query: str
    platform: str = "uword"

class ArticleSearchResponse(BaseModel):
    articles: list[dict]

@app.post("/api/search-articles", response_model=ArticleSearchResponse)
async def search_articles(req: ArticleSearchRequest):
    """Gemini を使って最新記事・トレンドを検索してリスト返却"""
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        return ArticleSearchResponse(articles=[])

    prompt = f"""以下のキーワードに関連する、最近（2024年以降）の日本語記事・ニュース・トレンドを5件教えてください。
キーワード: {req.query}

各記事について以下のJSON形式で返してください:
[
  {{
    "title": "記事タイトル",
    "summary": "100文字以内の要約",
    "topic": "投稿ネタとして使えるポイント",
    "estimated_virality": "high/medium/low"
  }}
]
JSON配列のみを返してください。"""

    try:
        import urllib.request as _urlreq
        gemini_url = (f'https://generativelanguage.googleapis.com/v1beta/models/'
                      f'gemini-2.0-flash:generateContent?key={api_key}')
        body = json.dumps({
            'contents': [{'parts': [{'text': prompt}]}],
            'generationConfig': {'responseMimeType': 'application/json'}
        }).encode('utf-8')
        http_req = _urlreq.Request(gemini_url, data=body,
                                   headers={'Content-Type': 'application/json'}, method='POST')
        loop = asyncio.get_event_loop()
        def _fetch():
            with _urlreq.urlopen(http_req, timeout=30) as r:
                return json.loads(r.read())
        resp = await loop.run_in_executor(None, _fetch)
        text = resp['candidates'][0]['content']['parts'][0]['text']
        articles = json.loads(text)
        if not isinstance(articles, list):
            articles = []
        return ArticleSearchResponse(articles=articles)
    except Exception as e:
        _logger.warning("search_articles error: %s", e)
        return ArticleSearchResponse(articles=[])
