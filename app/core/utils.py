"""通用工具：视频扫描、文件名清洗、时间与体积格式化。"""
from __future__ import annotations

import os
import re
from typing import Iterable, List

VIDEO_EXTENSIONS = {
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm",
    ".m4v", ".mpg", ".mpeg", ".ts", ".3gp", ".vob", ".rmvb",
}

IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tif", ".tiff",
}

_INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def is_video(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in VIDEO_EXTENSIONS


def is_image(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in IMAGE_EXTENSIONS


def safe_name(name: str) -> str:
    """把视频文件名处理成合法的 Windows 文件夹/文件名片段。"""
    name = _INVALID_CHARS.sub("_", name).strip(" .")
    return name or "video"


def _scan(paths: Iterable[str], recursive: bool, predicate) -> List[str]:
    """接受文件路径与文件夹路径，去重后按类型过滤。"""
    found: List[str] = []
    seen = set()

    def add(file_path: str) -> None:
        norm = os.path.normpath(os.path.abspath(file_path))
        key = norm.lower()
        if key not in seen and os.path.isfile(norm) and predicate(norm):
            seen.add(key)
            found.append(norm)

    for path in paths:
        if os.path.isfile(path):
            add(path)
        elif os.path.isdir(path):
            if recursive:
                for root, _dirs, files in os.walk(path):
                    for f in files:
                        add(os.path.join(root, f))
            else:
                for f in os.listdir(path):
                    add(os.path.join(path, f))
    return found


def scan_videos(paths: Iterable[str], recursive: bool = True) -> List[str]:
    return _scan(paths, recursive, is_video)


def scan_images(paths: Iterable[str], recursive: bool = True) -> List[str]:
    return _scan(paths, recursive, is_image)


def format_duration(seconds: float) -> str:
    if seconds <= 0:
        return "--:--"
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def format_size(num_bytes: float) -> str:
    value = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(value) < 1024.0:
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024.0
    return f"{value:.1f} PB"


def format_count(n: int) -> str:
    return f"{n:,}"
