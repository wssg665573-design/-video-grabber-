# -*- coding: utf-8 -*-
"""小红书解析器：使用小红书 H5/APP 嵌入接口"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Optional

import httpx

from .base import BaseParser, VideoInfo
from .generic import GenericParser

logger = logging.getLogger("video-downloader")

_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.49 NetType/WIFI Language/zh_CN"


class XiaohongshuParser(BaseParser):
    name = "xiaohongshu"
    domains = ("xiaohongshu.com", "xhslink.com")

    async def parse(self, url: str) -> VideoInfo:
        info = await self._fetch(url)
        if info:
            return self._to_video_info(url, info)
        logger.info("小红书专用解析失败，回退 yt-dlp: %s", url)
        return await GenericParser().parse(url)

    async def _fetch(self, url: str) -> Optional[Dict[str, Any]]:
        headers = {"User-Agent": _UA, "Referer": "https://www.xiaohongshu.com/"}
        try:
            async with httpx.AsyncClient(headers=headers, timeout=20, follow_redirects=True) as client:
                resp = await client.get(url)
                html = resp.text
                state = re.search(r"window\.__INITIAL_STATE__\s*=\s*(\{.+?\})\s*</script>", html, re.DOTALL)
                if not state:
                    return None
                # 默认不解析深层，交给 yt-dlp 兜底
                data = json.loads(state.group(1))
                notes = data.get("noteData", {}).get("data", {}).get("note") or {}
                if notes:
                    return notes
        except Exception as exc:  # noqa: BLE001
            logger.warning("小红书解析失败 %s: %s", url, exc)
        return None

    def _to_video_info(self, url: str, info: Dict[str, Any]) -> VideoInfo:
        video = info.get("video") or {}
        media = video.get("media", {}) or {}
        stream = (media.get("stream") or {}).get("h264") or {}
        urls = stream.get("masterUrl") or stream.get("backupUrls") or []
        if isinstance(urls, str):
            urls = [urls]
        cover = (info.get("imageList") or [{}])[0].get("urlDefault") if info.get("imageList") else None
        return VideoInfo(
            url=url,
            platform=self.name,
            title=info.get("title") or "小红书视频",
            author=(info.get("user") or {}).get("nickname"),
            thumbnail=cover,
            cover=cover,
            video_url=urls[0] if urls else None,
            duration=info.get("duration"),
            ext="mp4",
            description=info.get("desc"),
        )
