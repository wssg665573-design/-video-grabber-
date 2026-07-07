# -*- coding: utf-8 -*-
"""解析器注册中心"""
from __future__ import annotations

import asyncio
import logging
from typing import Iterable, List, Optional

from .base import BaseParser, VideoInfo
from .douyin import DouyinParser
from .kuaishou import KuaishouParser
from .xiaohongshu import XiaohongshuParser
from .bilibili import BilibiliParser
from .weibo import WeiboParser
from .generic import GenericParser

logger = logging.getLogger("video-downloader")

_PLATFORM_PARSERS = [
    DouyinParser(),
    KuaishouParser(),
    XiaohongshuParser(),
    BilibiliParser(),
    WeiboParser(),
    GenericParser(),
]


class ParserRegistry:
    """解析器注册表：根据 URL 自动选择最匹配的解析器"""

    def __init__(self, parsers: Optional[Iterable[BaseParser]] = None) -> None:
        self._parsers: List[BaseParser] = list(parsers) if parsers is not None else list(_PLATFORM_PARSERS)

    def find(self, url: str) -> BaseParser:
        for parser in self._parsers:
            if parser.can_handle(url):
                return parser
        return self._parsers[-1]

    async def parse(self, url: str) -> VideoInfo:
        parser = self.find(url)
        logger.info("使用解析器 %s 处理 %s", parser.name, url)
        try:
            return await parser.parse(url)
        except Exception as exc:  # noqa: BLE001
            logger.exception("解析失败: %s", url)
            return VideoInfo(url=url, platform=parser.name, error=str(exc))

    async def parse_many(self, urls: Iterable[str]) -> List[VideoInfo]:
        urls = [u.strip() for u in urls if u and u.strip()]
        return await asyncio.gather(*(self.parse(u) for u in urls))


_default_registry: Optional[ParserRegistry] = None


def get_registry() -> ParserRegistry:
    global _default_registry
    if _default_registry is None:
        _default_registry = ParserRegistry()
    return _default_registry
