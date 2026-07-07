# -*- coding: utf-8 -*-
"""快手解析器：使用快手 H5 接口获取无水印视频"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Optional

import httpx

from .base import BaseParser, VideoInfo
from .generic import GenericParser

logger = logging.getLogger("video-downloader")

_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1"
_H5 = "https://h5.p.kuaishou.com/fkw/apollo/work-aggregation"
_SHARE_RE = re.compile(r"https?://[^\s]+")


class KuaishouParser(BaseParser):
    name = "kuaishou"
    domains = ("kuaishou.com", "chenzhongtech.com", "gifshow.com")

    async def parse(self, url: str) -> VideoInfo:
        info = await self._fetch_photo(url)
        if info:
            return self._to_video_info(url, info)
        logger.info("快手专用解析失败，回退 yt-dlp: %s", url)
        return await GenericParser().parse(url)

    async def _fetch_photo(self, url: str) -> Optional[Dict[str, Any]]:
        headers = {
            "User-Agent": _UA,
            "Referer": "https://www.kuaishou.com/",
            "Accept": "application/json",
        }
        try:
            async with httpx.AsyncClient(headers=headers, timeout=20, follow_redirects=True) as client:
                resp = await client.get(url)
                html = resp.text
                match = re.search(r"window\.__APOLLO_STATE__\s*=\s*(\{.+?\})\s*</script>", html, re.DOTALL)
                if not match:
                    return None
                data = json.loads(match.group(1))
                # 在数据中找 photo 信息
                for key, value in data.items():
                    if isinstance(value, dict) and "photoUrl" in value:
                        return value
                return None
        except Exception as exc:  # noqa: BLE001
            logger.warning("快手解析失败 %s: %s", url, exc)
            return None

    def _to_video_info(self, url: str, info: Dict[str, Any]) -> VideoInfo:
        photo_url = info.get("photoUrl") or info.get("photoH265Url") or info.get("videoUrl")
        cover = info.get("coverUrl") or info.get("coverThumb")
        title = info.get("caption") or info.get("title") or "快手视频"
        return VideoInfo(
            url=url,
            platform=self.name,
            title=title,
            author=(info.get("user") or {}).get("name") if isinstance(info.get("user"), dict) else None,
            thumbnail=cover,
            cover=cover,
            video_url=photo_url,
            duration=info.get("duration") / 1000.0 if info.get("duration") else None,
            width=info.get("width"),
            height=info.get("height"),
            ext="mp4",
        )
