# -*- coding: utf-8 -*-
"""B站解析器：通过 B 站开放 API 获取视频直链（最高画质）"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional

import httpx

from .base import BaseParser, VideoInfo
from .generic import GenericParser

logger = logging.getLogger("video-downloader")

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
_BV_RE = re.compile(r"BV([0-9A-Za-z]+)")
_AV_RE = re.compile(r"av(\d+)")


class BilibiliParser(BaseParser):
    name = "bilibili"
    domains = ("bilibili.com", "b23.tv", "bili2233.cn")

    async def parse(self, url: str) -> VideoInfo:
        bvid = self._extract_bvid(url)
        if bvid:
            info = await self._fetch_view(bvid)
            if info:
                play = await self._fetch_playurl(bvid, info.get("cid"), info.get("qn"))
                if play:
                    return self._to_video_info(url, info, play)
        logger.info("B 站专用解析失败，回退 yt-dlp: %s", url)
        return await GenericParser().parse(url)

    def _extract_bvid(self, url: str) -> Optional[str]:
        m = _BV_RE.search(url)
        if m:
            return "BV" + m.group(1)
        m = _AV_RE.search(url)
        if m:
            return m.group(1)
        return None

    async def _fetch_view(self, bvid: str) -> Optional[Dict[str, Any]]:
        url = "https://api.bilibili.com/x/web-interface/view"
        params = {"bvid": bvid} if bvid.startswith("BV") else {"aid": bvid}
        headers = {"User-Agent": _UA, "Referer": "https://www.bilibili.com/", "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}
        try:
            async with httpx.AsyncClient(headers=headers, timeout=15) as client:
                resp = await client.get(url, params=params)
                data = resp.json()
                if data.get("code") != 0:
                    return None
                return data.get("data") or {}
        except Exception as exc:  # noqa: BLE001
            logger.warning("B 站 view 接口失败 %s: %s", bvid, exc)
            return None

    async def _fetch_playurl(self, bvid: str, cid: Optional[int], qn: Optional[int]) -> Optional[Dict[str, Any]]:
        if not cid:
            return None
        params = {
            "bvid": bvid if bvid.startswith("BV") else "",
            "cid": cid,
            "qn": qn or 80,
            "fnval": 1,
            "fnver": 0,
            "fourk": 1,
            "platform": "html5",
            "high_quality": 1,
        }
        params["avid"] = bvid if not bvid.startswith("BV") else ""
        url = "https://api.bilibili.com/x/player/playurl"
        headers = {"User-Agent": _UA, "Referer": "https://www.bilibili.com/", "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}
        try:
            async with httpx.AsyncClient(headers=headers, timeout=20) as client:
                resp = await client.get(url, params=params)
                data = resp.json()
                if data.get("code") != 0:
                    return None
                return data.get("data") or {}
        except Exception as exc:  # noqa: BLE001
            logger.warning("B 站 playurl 接口失败 %s: %s", bvid, exc)
            return None

    def _to_video_info(self, url: str, info: Dict[str, Any], play: Dict[str, Any]) -> VideoInfo:
        durls = play.get("durl") or []
        video_url = durls[0].get("url") if durls else None
        cover = info.get("pic")
        owner = info.get("owner") or {}
        return VideoInfo(
            url=url,
            platform=self.name,
            title=info.get("title") or "B 站视频",
            author=owner.get("name"),
            thumbnail=cover,
            cover=cover,
            video_url=video_url,
            duration=info.get("duration"),
            width=None,
            height=None,
            size=durls[0].get("size") if durls else None,
            ext="mp4",
            description=info.get("desc"),
            extras={"headers": {"Referer": "https://www.bilibili.com/", "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}},
        )

