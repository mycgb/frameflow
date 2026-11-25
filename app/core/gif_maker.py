"""把一组图片合成为 GIF 动画的引擎（不依赖 GUI）。"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Callable, List, Optional

from PIL import Image

CheckpointFn = Callable[[int], None]
ProgressFn = Callable[["GifProgress"], None]


class GifCanceled(Exception):
    """用户取消任务时由 checkpoint 抛出。"""


@dataclass
class GifConfig:
    output_path: str = ""
    delay_ms: int = 100          # 每帧停留时间
    loop: int = 0                # 0 = 无限循环
    resize_mode: str = "original"  # original / width / height / scale
    resize_value: int = 100
    reverse: bool = False
    optimize: bool = True

    def normalized(self) -> "GifConfig":
        cfg = self
        cfg.delay_ms = max(20, min(10000, int(cfg.delay_ms)))
        cfg.loop = max(0, int(cfg.loop))
        if cfg.resize_mode not in ("original", "width", "height", "scale"):
            cfg.resize_mode = "original"
        cfg.resize_value = max(1, int(cfg.resize_value))
        return cfg


@dataclass
class GifProgress:
    index: int
    total: int
    percent: float


@dataclass
class GifResult:
    output_path: str
    frames: int
    size_bytes: int
    elapsed: float
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error


class GifMaker:
    def create(
        self,
        images: List[str],
        config: GifConfig,
        checkpoint: Optional[CheckpointFn] = None,
        on_progress: Optional[ProgressFn] = None,
    ) -> GifResult:
        cfg = config.normalized()
        started = time.monotonic()
        out_path = os.path.abspath(cfg.output_path)
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

        frames: List[Image.Image] = []
        error = ""
        try:
            total = len(images)
            for index, path in enumerate(images):
                if checkpoint:
                    checkpoint(index)

                with Image.open(path) as source:
                    source.seek(0)  # 多帧图片只取第一帧
                    if source.mode in ("RGBA", "LA") or "transparency" in source.info:
                        rgba = source.convert("RGBA")
                        background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
                        background.alpha_composite(rgba)
                        frame = background.convert("RGB")
                    else:
                        frame = source.convert("RGB")
                    frame = self._resize(frame, cfg)
                    frames.append(frame.copy())

                if on_progress:
                    on_progress(GifProgress(index + 1, total, (index + 1) / max(1, total) * 100.0))

            if cfg.reverse:
                frames.reverse()

            if len(frames) < 2:
                error = "至少需要 2 张图片才能生成动画"
            else:
                if checkpoint:
                    checkpoint(len(images))  # 编码阶段也允许取消
                frames[0].save(
                    out_path,
                    save_all=True,
                    append_images=frames[1:],
                    duration=cfg.delay_ms,
                    loop=cfg.loop,
                    optimize=cfg.optimize,
                    disposal=2,
                )
        except GifCanceled:
            error = "已取消"
        except Exception as exc:  # noqa: BLE001 - 单张坏图不应让整个程序崩溃
            error = f"{type(exc).__name__}: {exc}"
        finally:
            for frame in frames:
                frame.close()

        if error and os.path.isfile(out_path):
            try:
                os.remove(out_path)  # 失败或取消时清掉半成品
            except OSError:
                pass
        size = os.path.getsize(out_path) if os.path.isfile(out_path) and not error else 0
        return GifResult(
            output_path=out_path, frames=len(frames),
            size_bytes=size, elapsed=time.monotonic() - started, error=error,
        )

    @staticmethod
    def _resize(image: Image.Image, cfg: GifConfig) -> Image.Image:
        w, h = image.size
        if cfg.resize_mode == "original":
            return image
        if cfg.resize_mode == "width":
            nw = max(1, int(cfg.resize_value))
            nh = max(1, round(h * nw / w))
        elif cfg.resize_mode == "height":
            nh = max(1, int(cfg.resize_value))
            nw = max(1, round(w * nh / h))
        else:
            factor = cfg.resize_value / 100.0
            nw, nh = max(1, round(w * factor)), max(1, round(h * factor))
        if (nw, nh) == (w, h):
            return image
        return image.resize((nw, nh), Image.Resampling.LANCZOS)
