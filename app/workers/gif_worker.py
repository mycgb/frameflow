"""GIF 合成后台线程。"""
from __future__ import annotations

import threading
import time
from typing import List

from PySide6.QtCore import QThread, Signal

from app.core.gif_maker import GifCanceled, GifConfig, GifMaker, GifProgress


class GifWorker(QThread):
    sig_progress = Signal(int, int, float)   # 当前, 总数, 百分比
    sig_log = Signal(str, str)
    sig_done = Signal(int, int, float, bool)  # 帧数, 字节数, 用时, 是否取消
    sig_item_done = Signal(int)              # 已处理到第几张

    def __init__(self, images: List[str], config: GifConfig, maker: GifMaker, parent=None) -> None:
        super().__init__(parent)
        self.images = list(images)
        self.config = config
        self.maker = maker
        self._pause_event = threading.Event()
        self._cancelled = threading.Event()

    def pause(self) -> None:
        self._pause_event.set()
        self.sig_log.emit("warn", "任务已暂停")

    def resume(self) -> None:
        self._pause_event.clear()
        self.sig_log.emit("info", "任务已继续")

    def cancel(self) -> None:
        self._cancelled.set()
        self._pause_event.clear()
        self.sig_log.emit("warn", "正在取消任务…")

    @property
    def is_paused(self) -> bool:
        return self._pause_event.is_set()

    def _checkpoint(self, _index: int) -> None:
        if self._cancelled.is_set():
            raise GifCanceled()
        while self._pause_event.is_set():
            if self._cancelled.is_set():
                raise GifCanceled()
            self._pause_event.wait(0.05)

    def _on_progress(self, info: GifProgress) -> None:
        self.sig_progress.emit(info.index, info.total, info.percent)
        self.sig_item_done.emit(info.index)

    def run(self) -> None:  # noqa: D102
        started = time.monotonic()
        self.sig_log.emit("info", f"开始合成 GIF，共 {len(self.images)} 张图片")
        result = self.maker.create(
            self.images, self.config,
            checkpoint=self._checkpoint,
            on_progress=self._on_progress,
        )
        canceled = result.error == "已取消"
        if result.ok:
            self.sig_log.emit("success", f"GIF 已生成：{result.output_path}")
        elif canceled:
            self.sig_log.emit("warn", "任务已取消")
        else:
            self.sig_log.emit("error", f"GIF 生成失败：{result.error}")
        self.sig_done.emit(result.frames, result.size_bytes, time.monotonic() - started, canceled)
