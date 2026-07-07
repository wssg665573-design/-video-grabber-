# -*- coding: utf-8 -*-
# 微博视频解析：复用通用解析器（yt-dlp 已支持）
from __future__ import annotations

from .base import BaseParser, VideoInfo
from .generic import GenericParser


class WeiboParser(BaseParser):
    name = "weibo"
    domains = ("weibo.com", "weibo.cn", "wb.cn")

    def __init__(self) -> None:
        self._generic = GenericParser()

    async def parse(self, url: str) -> VideoInfo:
        info = await self._generic.parse(url)
        if not info.error:
            info.platform = self.name
        return info
