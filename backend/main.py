# -*- coding: utf-8 -*-
# 视频去水印下载服务 - FastAPI 主程序（生产级）
from __future__ import annotations

import io
import logging
import os
import re
import secrets
import time
import uuid
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from parsers import get_registry

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("video-downloader")

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = (BASE_DIR.parent / "frontend").resolve()

API_KEY = os.getenv("API_KEY", "").strip()
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").strip()
ALLOW_ORIGINS = [o.strip() for o in os.getenv("ALLOW_ORIGINS", "*").split(",") if o.strip()] or ["*"]
MAX_BATCH = int(os.getenv("MAX_BATCH", "20"))
MAX_FILE_BYTES = int(os.getenv("MAX_FILE_BYTES", str(200 * 1024 * 1024)))

_PLATFORM_LIST = [
    {"id": "douyin", "name": "抖音", "icon": "🎵", "color": "#000000"},
    {"id": "kuaishou", "name": "快手", "icon": "⚡", "color": "#FF6600"},
    {"id": "xiaohongshu", "name": "小红书", "icon": "📕", "color": "#FE2C55"},
    {"id": "bilibili", "name": "B 站", "icon": "📺", "color": "#00A1D6"},
    {"id": "weibo", "name": "微博", "icon": "🔥", "color": "#E6162D"},
    {"id": "youtube", "name": "YouTube", "icon": "▶️", "color": "#FF0000"},
    {"id": "generic", "name": "其他", "icon": "🌐", "color": "#666666"},
]


def _rate_key(request: Request) -> str:
    key = request.headers.get("x-api-key", "").strip()
    if key:
        return "k:" + key[:16]
    return get_remote_address(request)


limiter = Limiter(key_func=_rate_key)

# Simple in-memory rate limiter
import time as _time
from collections import defaultdict as _defaultdict
_rate_store: dict = _defaultdict(list)

def _enforce_rate(scope: str, key: str, limit: int, window: int) -> None:
    """Raise 429 if the (scope, key) exceeded limit in last `window` seconds."""
    full_key = f"{scope}:{key}"
    now = _time.time()
    bucket = _rate_store[full_key]
    # drop old
    cutoff = now - window
    while bucket and bucket[0] < cutoff:
        bucket.pop(0)
    if len(bucket) >= limit:
        retry = int(window - (now - bucket[0])) + 1
        raise HTTPException(status_code=429, detail=f"请求过于频繁，请 {retry}s 后再试", headers={"Retry-After": str(retry)})
    bucket.append(now)




@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 60)
    logger.info("VideoGrab 启动中...")
    logger.info("API_KEY: %s", "已启用" if API_KEY else "未启用（开放模式）")
    logger.info("PUBLIC_BASE_URL: %s", PUBLIC_BASE_URL or "(自动检测)")
    logger.info("ALLOW_ORIGINS: %s", ALLOW_ORIGINS)
    logger.info("MAX_BATCH: %s, MAX_FILE_BYTES: %.0f MB", MAX_BATCH, MAX_FILE_BYTES / 1024 / 1024)
    logger.info("=" * 60)
    yield
    logger.info("VideoGrab 关闭")


app = FastAPI(
    title="VideoGrab 视频去水印批量下载",
    description="支持抖音 / 快手 / 小红书 / B 站 / 微博 / YouTube 等平台。**仅供个人学习与备份，请勿用于侵权用途。**",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOW_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
    request.state.rid = rid
    start = time.time()
    try:
        response = await call_next(request)
    except Exception as exc:
        logger.exception("[%s] %s %s -> 500: %s", rid, request.method, request.url.path, exc)
        return JSONResponse({"detail": "服务器内部错误", "request_id": rid}, status_code=500)
    response.headers["X-Request-ID"] = rid
    response.headers["X-Response-Time"] = f"{(time.time() - start) * 1000:.1f}ms"
    return response


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": f"请求过于频繁，请稍后再试（{exc.detail}）", "request_id": getattr(request.state, "rid", "")},
        headers={"Retry-After": "60"},
    )


def check_api_key(request: Request):
    if not API_KEY:
        return
    key = request.headers.get("x-api-key", "").strip() or request.query_params.get("api_key", "").strip()
    if not secrets.compare_digest(key, API_KEY):
        raise HTTPException(status_code=401, detail="API Key 无效")


class ParseRequest(BaseModel):
    urls: List[str] = Field(..., description="视频链接列表")


class BatchDownloadRequest(BaseModel):
    items: List[Dict[str, Any]] = Field(..., description="由 /api/parse 返回的 items 列表")
    zip_name: Optional[str] = "videos.zip"


def _sanitize_filename(name: str, fallback: str = "video") -> str:
    name = re.sub(r"[\\/\\:\\*\\?\"<>\\|]", "_", name or "").strip()
    name = re.sub(r"\\s+", " ", name)
    return name[:80] or fallback


@app.get("/api/health")
async def health() -> Dict[str, Any]:
    return {"status": "ok", "version": app.version, "time": int(time.time())}


@app.get("/api/platforms")
async def platforms() -> List[Dict[str, str]]:
    return _PLATFORM_LIST


@app.get("/robots.txt", response_class=PlainTextResponse)
async def robots() -> str:
    base = PUBLIC_BASE_URL.rstrip("/") if PUBLIC_BASE_URL else ""
    body_lines = ["User-agent: *", "Allow: /", "Disallow: /api/"]
    if base:
        body_lines.append(f"Sitemap: {base}/sitemap.xml")
    return chr(10).join(body_lines)


_TOS_HTML = """<!doctype html>
<html lang=zh-CN><head><meta charset=utf-8>
<title>使用条款 · VideoGrab</title>
<style>
body{font-family:-apple-system,BlinkMacSystemFont,"PingFang SC",Microsoft YaHei,sans-serif;max-width:760px;margin:40px auto;padding:0 20px;line-height:1.75;color:#222;background:#fafafa}
h1{color:#111}.box{background:#fff;padding:24px 28px;border-radius:12px;box-shadow:0 2px 12px rgba(0,0,0,.05);border:1px solid #eee}
ul{padding-left:22px}li{margin:6px 0}a{color:#6366f1;text-decoration:none}
small{color:#888}
</style></head><body>
<div class=box>
<h1>使用条款 · Terms of Service</h1>
<p><small>最后更新：2026-07-08</small></p>
<h2>允许的用途</h2>
<ul>
<li>个人对自己拥有版权或获得授权的视频进行备份。</li>
<li>用于学习、研究、调试等非商业用途。</li>
</ul>
<h2>禁止的用途</h2>
<ul>
<li>下载未授权的他人作品并再次发布、二次售卖。</li>
<li>用于商业牟利或大规模爬取。</li>
<li>绕过平台付费墙或地区限制。</li>
<li>任何违反所在国家/地区法律法规及平台服务条款的行为。</li>
</ul>
<h2>免责声明</h2>
<ul>
<li>所有视频版权归原作者及发布平台所有。</li>
<li>本服务按"现状"提供，不保证持续可用、不保证解析准确。</li>
<li>使用本服务产生的任何法律责任由使用者本人承担。</li>
<li>运营者保留随时终止服务、调整限额的权利。</li>
</ul>
<p><a href="/">← 返回首页</a></p>
</div></body></html>"""


@app.get("/tos", response_class=HTMLResponse)
async def tos() -> str:
    return _TOS_HTML


@app.post("/api/parse")
async def parse_videos(request: Request, req: ParseRequest) -> Dict[str, Any]:
    _enforce_rate("parse", _rate_key(request), 30, 60)
    urls = [u.strip() for u in req.urls if u and u.strip()]
    if not urls:
        raise HTTPException(status_code=400, detail="链接不能为空")
    if len(urls) > MAX_BATCH:
        raise HTTPException(status_code=400, detail=f"单次最多 {MAX_BATCH} 个链接")
    registry = get_registry()
    results = await registry.parse_many(urls)
    return {"count": len(results), "results": [r.to_dict() for r in results]}


@app.get("/api/download")
async def download_single(request: Request, url: str = Query(..., description="原始视频链接")):
    _enforce_rate("download", _rate_key(request), 60, 60)
    registry = get_registry()
    info = await registry.parse(url)
    if not info.ok:
        raise HTTPException(status_code=400, detail=info.error or "解析失败")
    return await _stream_remote(info.video_url)


async def _stream_remote(url: str) -> StreamingResponse:
    async def iterator():
        async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
            async with client.stream("GET", url) as resp:
                resp.raise_for_status()
                async for chunk in resp.aiter_bytes(64 * 1024):
                    yield chunk

    headers = {}
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            head = await client.head(url)
            headers = dict(head.headers)
    except Exception:
        pass
    content_length = headers.get("content-length")
    content_type = headers.get("content-type") or "application/octet-stream"
    resp_headers = {}
    if content_length:
        resp_headers["Content-Length"] = content_length
    return StreamingResponse(iterator(), media_type=content_type, headers=resp_headers)


@app.post("/api/batch-download")
async def batch_download(request: Request, req: BatchDownloadRequest):
    _enforce_rate("batch", _rate_key(request), 15, 60)
    if not req.items:
        raise HTTPException(status_code=400, detail="缺少下载项")
    if len(req.items) > MAX_BATCH:
        raise HTTPException(status_code=400, detail=f"批量最多 {MAX_BATCH} 项")
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for idx, item in enumerate(req.items, 1):
            src_url = item.get("video_url") or item.get("url")
            title = item.get("title") or f"video_{idx}"
            platform = item.get("platform") or "generic"
            ext = item.get("ext") or "mp4"
            fname = f"{idx:02d}_{platform}_{_sanitize_filename(title)}.{ext}"
            if not src_url:
                zf.writestr(fname + ".err.txt", "missing video url")
                continue
            extra_headers = (item.get("extras") or {}).get("headers") or {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            }
            try:
                async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
                    async with client.stream("GET", src_url, headers=extra_headers) as resp:
                        resp.raise_for_status()
                        data = b""
                        async for chunk in resp.aiter_bytes(64 * 1024):
                            data += chunk
                            if len(data) > MAX_FILE_BYTES:
                                raise RuntimeError(f"文件超过 {MAX_FILE_BYTES // 1024 // 1024}MB 限制")
                        zf.writestr(fname, data)
            except Exception as exc:
                zf.writestr(fname + ".err.txt", f"download failed: {exc}")
    zip_buf.seek(0)
    headers_out = {"Content-Disposition": f"attachment; filename={req.zip_name or 'videos.zip'}"}
    return StreamingResponse(zip_buf, media_type="application/zip", headers=headers_out)


@app.get("/api/manifest.json")
async def manifest() -> JSONResponse:
    return JSONResponse({
        "name": "VideoGrab 视频去水印批量下载",
        "short_name": "VideoGrab",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#0f172a",
        "theme_color": "#6366f1",
        "icons": [],
    })


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    index_file = FRONTEND_DIR / "index.html"
    if not index_file.exists():
        return HTMLResponse("<h1>前端未构建</h1>", status_code=500)
    return HTMLResponse(index_file.read_text(encoding="utf-8"))


if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, workers=int(os.getenv("WORKERS", "2")), proxy_headers=True, forwarded_allow_ips="*")
