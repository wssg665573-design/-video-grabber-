# -*- coding: utf-8 -*-
"""抖音解析器：优先走 iesdouyin 接口，无水印；失败则回退 yt-dlp"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Dict, Optional

import httpx

from .base import BaseParser, VideoInfo
from .generic import GenericParser

logger = logging.getLogger("video-downloader")

_UA_MOBILE = "Mozilla/5.0 (Linux; Android 12; Pixel 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36"
_API = "https://www.iesdouyin.com/web/api/v2/aweme/iteminfo/"

_SHARE_DOMAINS = ("douyin.com", "iesdouyin.com", "v.douyin.com")

_VIDEO_ID_RE = re.compile(r"(?:video|note|modal_id)/(\d+)|item_ids=(\d+)|/(\d{15,20})")


class DouyinParser(BaseParser):
    name = "douyin"
    domains = _SHARE_DOMAINS

    async def parse(self, url: str) -> VideoInfo:
        video_id = await self._extract_video_id(url)
        if video_id:
            info = await self._fetch_api(video_id)
            if info:
                return self._to_video_info(url, info)
        # 回退 yt-dlp
        logger.info("抖音 API 解析失败，回退 yt-dlp: %s", url)
        return await GenericParser().parse(url)

    async def _extract_video_id(self, url: str) -> Optional[str]:
        match = _VIDEO_ID_RE.search(url)
        if match:
            for grp in match.groups():
                if grp:
                    return grp
        # 处理短链 v.douyin.com/xxx
        try:
            async with httpx.AsyncClient(
                headers={"User-Agent": _UA_MOBILE}, follow_redirects=True, timeout=15
            ) as client:
                resp = await client.get(url)
                final_url = str(resp.url)
                match = _VIDEO_ID_RE.search(final_url)
                if match:
                    for grp in match.groups():
                        if grp:
                            return grp
                # 找页面里嵌入的视频 ID
                match = re.search(r"video/(\d+)", resp.text)
                if match:
                    return match.group(1)
        except Exception as exc:  # noqa: BLE001
            logger.warning("解析抖音短链失败 %s: %s", url, exc)
        return None

    async def _fetch_api(self, video_id: str) -> Optional[Dict[str, Any]]:
        params = {"item_ids": video_id}
        headers = {
            "User-Agent": _UA_MOBILE,
            "Referer": "https://www.douyin.com/",
        }
        try:
            async with httpx.AsyncClient(headers=headers, timeout=20) as client:
                resp = await client.get(_API, params=params)
                if resp.status_code != 200:
                    return None
                data = resp.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning("调用抖音 API 失败 %s: %s", video_id, exc)
            return None
        items = (data or {}).get("item_list") or []
        return items[0] if items else None

    def _to_video_info(self, url: str, info: Dict[str, Any]) -> VideoInfo:
        video = info.get("video") or {}
        play = video.get("play_addr") or {}
        url_list = play.get("url_list") or []
        video_url = url_list[0] if url_list else None
        cover_list = video.get("cover", {}).get("url_list") or video.get("origin_cover", {}).get("url_list") or []
        music = info.get("music") or {}
        music_url = (music.get("play_url") or {}).get("url_list", [None])[0]
        desc = info.get("desc") or ""
        author = (info.get("author") or {}).get("nickname")
        duration_ms = video.get("duration")
        duration = duration_ms / 1000.0 if duration_ms else None
        ratio = video.get("ratio") or "default"
        ext = "mp4"
        return VideoInfo(
            url=url,
            platform=self.name,
            title=desc or "抖音视频",
            author=author,
            thumbnail=cover_list[0] if cover_list else None,
            cover=cover_list[-1] if cover_list else None,
            video_url=video_url,
            audio_url=music_url,
            duration=duration,
            width=video.get("width"),
            height=video.get("height"),
            size=(video.get("play_addr", {}) or {}).get("data_size"),
            ext=ext,
            description=desc,
            music=(music.get("title") if music else None),
            extras={"ratio": ratio, "video_id": info.get("aweme_id")},
        )
