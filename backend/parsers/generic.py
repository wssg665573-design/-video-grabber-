# -*- coding: utf-8 -*-
"""通用解析器：基于 yt-dlp，支持大多数平台"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Dict, Optional

from .base import BaseParser, VideoInfo

try:
    import yt_dlp
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("需要安装 yt-dlp: pip install yt-dlp") from exc

logger = logging.getLogger("video-downloader")

_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"


class GenericParser(BaseParser):
    """兜底解析器，依靠 yt-dlp 处理绝大多数主流站点"""

    name = "generic"
    domains = ()  # 兜底，总是匹配

    def can_handle(self, url: str) -> bool:
        return True  # 兜底，registry 会优先调用更专门的解析器

    @staticmethod
    def _build_opts(extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        opts: Dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "skip_download": True,
            "format": "bestvideo*+bestaudio/best",
            "geo_bypass": True,
            "nocheckcertificate": True,
            "http_headers": {"User-Agent": _USER_AGENT},
        }
        if extra:
            opts.update(extra)
        return opts

    @staticmethod
    def _extract_video_url(info: Dict[str, Any]) -> Optional[str]:
        if not info:
            return None
        url = info.get("url")
        if url:
            return url
        formats = info.get("formats") or []
        if not formats:
            return None
        def score(fmt: Dict[str, Any]) -> tuple:
            has_video = fmt.get("vcodec") not in (None, "none")
            has_audio = fmt.get("acodec") not in (None, "none")
            height = fmt.get("height") or 0
            tbr = fmt.get("tbr") or 0
            return (has_video and has_audio, height, tbr)
        best = max(formats, key=score)
        return best.get("url")

    async def parse(self, url: str) -> VideoInfo:
        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(None, self._extract, url, None)
        if not info:
            return VideoInfo(url=url, platform=self.name, error="解析失败")
        return self._to_video_info(url, info)

    def _extract(self, url: str, extra: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        opts = self._build_opts(extra)
        with yt_dlp.YoutubeDL(opts) as ydl:
            try:
                return ydl.extract_info(url, download=False)
            except Exception as exc:  # noqa: BLE001
                logger.warning("yt-dlp 解析失败 %s: %s", url, exc)
                return {}

    def _to_video_info(self, url: str, info: Dict[str, Any]) -> VideoInfo:
        extractor = info.get("extractor") or self.name
        platform = info.get("extractor_key") or extractor.split(":")[0]
        return VideoInfo(
            url=url,
            platform=platform,
            title=info.get("title") or info.get("description", "")[:80],
            author=info.get("uploader") or info.get("creator"),
            thumbnail=info.get("thumbnail"),
            cover=info.get("thumbnails", [{}])[-1].get("url") if info.get("thumbnails") else None,
            video_url=self._extract_video_url(info),
            audio_url=None,
            duration=info.get("duration"),
            width=info.get("width"),
            height=info.get("height"),
            size=info.get("filesize") or info.get("filesize_approx"),
            ext=info.get("ext"),
            description=info.get("description"),
            music=info.get("artist") or info.get("track"),
        )
