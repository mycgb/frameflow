"""视频逐帧导出引擎。

设计原则：
1. 不依赖 Qt / 任何 GUI 框架，可被 CLI、批处理脚本直接调用；
2. 每一帧都经过 checkpoint 回调，UI 层可据此实现暂停与取消；
3. 通过 processors 钩子预留水印、裁剪、滤镜等后续扩展点。
"""
from __future__ import annotations

import math
import os
import time
from dataclasses import dataclass
from typing import Callable, List, Optional

import cv2

from .config import ExtractConfig
from .utils import safe_name

CheckpointFn = Callable[[int], None]          # frame_index -> None
ProgressFn = Callable[["ProgressInfo"], None]


class ExtractCanceled(Exception):
    """用户取消任务时由 checkpoint 抛出。"""


@dataclass
class VideoInfo:
    path: str
    fps: float
    frame_count: int
    width: int
    height: int
    duration: float

    @property
    def resolution(self) -> str:
        return f"{self.width} x {self.height}"


@dataclass
class ProgressInfo:
    video_path: str
    frame_index: int
    total_frames: int
    saved: int
    percent: float

    @property
    def eta_text(self) -> str:
        return f"{self.saved} / {self.total_frames if self.total_frames else '?'} 帧"


@dataclass
class ExtractResult:
    video_path: str
    output_dir: str
    saved: int
    skipped: int
    elapsed: float
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error


def probe_video(path: str) -> VideoInfo:
    """读取视频元信息。无法打开时抛出 RuntimeError。"""
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        cap.release()
        raise RuntimeError(f"无法打开视频：{path}")

    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    if not math.isfinite(fps) or fps <= 0:
        fps = 25.0
    count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    duration = count / fps if count > 0 else 0.0
    cap.release()
    return VideoInfo(
        path=path, fps=fps, frame_count=count,
        width=width, height=height, duration=duration,
    )


class FrameExtractor:
    """逐帧导出器。可复用实例，通过 add_processor 挂接后续处理逻辑。"""

    def __init__(self) -> None:
        self.processors: List[Callable] = []

    def add_processor(self, fn: Callable) -> None:
        """注册帧处理器：fn(frame, frame_index, context) -> frame。"""
        self.processors.append(fn)

    def clear_processors(self) -> None:
        self.processors.clear()

    # ------------------------------------------------------------------
    def extract(
        self,
        video_path: str,
        config: ExtractConfig,
        checkpoint: Optional[CheckpointFn] = None,
        on_progress: Optional[ProgressFn] = None,
    ) -> ExtractResult:
        cfg = config.normalized()
        started = time.monotonic()
        info = probe_video(video_path)

        stem = safe_name(os.path.splitext(os.path.basename(video_path))[0])
        out_dir = cfg.output_dir
        if cfg.subfolder_per_video:
            out_dir = os.path.join(out_dir, stem)
        os.makedirs(out_dir, exist_ok=True)

        ext = "jpg" if cfg.image_format == "jpeg" else cfg.image_format
        write_params = self._write_params(cfg, ext)

        saved = 0
        skipped = 0
        error = ""
        cap = cv2.VideoCapture(video_path)
        try:
            # 起点定位：优先按毫秒（兼容可变帧率），失败时退回帧号
            if cfg.start_time > 0:
                cap.set(cv2.CAP_PROP_POS_MSEC, cfg.start_time * 1000.0)
                if cap.get(cv2.CAP_PROP_POS_MSEC) < cfg.start_time * 1000.0 * 0.5:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, int(cfg.start_time * info.fps))

            frame_index = 0
            step_ms = 1000.0 / cfg.frame_value  # per_second 模式下每张图的时间间隔
            next_second_frame = 0.0
            total = info.frame_count
            if cfg.frame_mode == "every_n":
                total = max(1, math.ceil(total / cfg.frame_value))
            elif cfg.frame_mode == "per_second":
                total = max(1, int(info.duration * cfg.frame_value))

            context = {"video_path": video_path, "info": info, "config": cfg}

            while True:
                if checkpoint:
                    checkpoint(frame_index)

                ok, frame = cap.read()
                if not ok:
                    break

                msec = float(cap.get(cv2.CAP_PROP_POS_MSEC) or 0.0)
                if cfg.end_time and msec > cfg.end_time * 1000.0:
                    break

                want = False
                if cfg.frame_mode == "all":
                    want = True
                elif cfg.frame_mode == "every_n":
                    want = frame_index % cfg.frame_value == 0
                else:  # per_second：按固定时间片取样，解码跳帧时也不会重复取同一片
                    want = msec >= next_second_frame
                    if want:
                        next_second_frame = (int(msec / step_ms) + 1) * step_ms

                if want:
                    processed = frame
                    for processor in self.processors:
                        processed = processor(processed, frame_index, context)
                        if processed is None:
                            processed = frame
                    processed = self._resize(processed, cfg)

                    filename = cfg.name_pattern.format(
                        name=stem, index=saved + skipped + 1,
                        frame=frame_index, fps=info.fps,
                    )
                    filename = safe_name(os.path.splitext(filename)[0]) + "." + ext
                    target = os.path.join(out_dir, filename)

                    if os.path.exists(target) and not cfg.overwrite:
                        skipped += 1
                    else:
                        if self._save_image(target, processed, ext, write_params):
                            saved += 1
                        else:
                            error = f"第 {frame_index} 帧写入失败：{target}"

                    if error:
                        break
                    if cfg.max_frames and saved >= cfg.max_frames:
                        break

                frame_index += 1
                if on_progress and (frame_index % 2 == 0 or frame_index == 1):
                    percent = min(100.0, frame_index / max(1, total) * 100.0)
                    on_progress(ProgressInfo(
                        video_path=video_path, frame_index=frame_index,
                        total_frames=total, saved=saved, percent=percent,
                    ))
        except ExtractCanceled:
            error = "已取消"
        except Exception as exc:  # noqa: BLE001 - 兜底，保证单个视频失败不影响队列
            error = f"{type(exc).__name__}: {exc}"
        finally:
            cap.release()

        if on_progress:
            on_progress(ProgressInfo(
                video_path=video_path, frame_index=frame_index if 'frame_index' in locals() else 0,
                total_frames=total if 'total' in locals() else info.frame_count,
                saved=saved, percent=100.0,
            ))

        return ExtractResult(
            video_path=video_path, output_dir=out_dir,
            saved=saved, skipped=skipped,
            elapsed=time.monotonic() - started, error=error,
        )

    # ------------------------------------------------------------------
    @staticmethod
    def _save_image(target: str, frame, ext: str, params: List[int]) -> bool:
        """用 imencode + 二进制写入代替 imwrite，兼容中文 / emoji 路径。"""
        try:
            ok, buffer = cv2.imencode("." + ext, frame, params)
            if not ok:
                return False
            with open(target, "wb") as fh:
                fh.write(buffer.tobytes())
            return True
        except OSError:
            return False

    @staticmethod
    def _write_params(cfg: ExtractConfig, ext: str) -> List[int]:
        if ext in ("jpg", "jpeg"):
            return [int(cv2.IMWRITE_JPEG_QUALITY), cfg.quality]
        if ext == "webp":
            return [int(cv2.IMWRITE_WEBP_QUALITY), cfg.quality]
        # PNG 的 compression 越大文件越小但越慢，方向与 quality 相反
        compression = int(round((100 - cfg.quality) / 100.0 * 9))
        return [int(cv2.IMWRITE_PNG_COMPRESSION), max(0, min(9, compression))]

    @staticmethod
    def _resize(frame, cfg: ExtractConfig):
        h, w = frame.shape[:2]
        if cfg.resize_mode == "original":
            return frame
        if cfg.resize_mode == "width":
            nw = max(1, int(cfg.resize_value))
            nh = max(1, round(h * nw / w))
        elif cfg.resize_mode == "height":
            nh = max(1, int(cfg.resize_value))
            nw = max(1, round(w * nh / h))
        else:  # scale
            factor = cfg.resize_value / 100.0
            nw, nh = max(1, round(w * factor)), max(1, round(h * factor))
        if nw == w and nh == h:
            return frame
        return cv2.resize(frame, (nw, nh), interpolation=cv2.INTER_AREA)
