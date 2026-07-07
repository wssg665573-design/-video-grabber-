# -*- coding: utf-8 -*-
"""解析器基类与统一数据结构"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass
class VideoInfo:
    """视频信息统一格式"""

    url: str
    platform: str
    title: str = ""
    author: Optional[str] = None
    thumbnail: Optional[str] = None
    cover: Optional[str] = None
    video_url: Optional[str] = None
    audio_url: Optional[str] = None
    duration: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    size: Optional[int] = None
    ext: Optional[str] = None
    description: Optional[str] = None
    music: Optional[str] = None
    error: Optional[str] = None
    extras: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.error is None and bool(self.video_url)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["ok"] = self.ok
        return d


class BaseParser(ABC):
    """所有平台解析器必须实现的接口"""

    name: str = "base"
    domains: tuple = ()

    def can_handle(self, url: str) -> bool:
        url_lower = url.lower()
        return any(d in url_lower for d in self.domains)

    @abstractmethod
    async def parse(self, url: str) -> VideoInfo:
        ...
