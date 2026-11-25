"""后台抽帧线程：把耗时解码移出 UI 线程，支持暂停 / 继续 / 取消。"""
from __future__ import annotations

import os
import threading
import time
from typing import List

from PySide6.QtCore import QThread, Signal

from app.core.config import ExtractConfig
from app.core.extractor import ExtractCanceled, ExtractResult, FrameExtractor, ProgressInfo


class ExtractWorker(QThread):
    sig_file_start = Signal(str, int, int)          # 路径, 当前序号, 总数
    sig_progress = Signal(str, int, int, int, float)  # 路径, 帧号, 总帧, 已保存, 百分比
    sig_file_done = Signal(str, int, int, float, str)  # 路径, 保存数, 跳过数, 用时, 错误
    sig_log = Signal(str, str)                      # 级别, 内容
    sig_all_done = Signal(int, float, bool)         # 总保存数, 总用时, 是否取消

    def __init__(
        self,
        tasks: List[str],
        config: ExtractConfig,
        extractor: FrameExtractor,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.tasks = list(tasks)
        self.config = config
        self.extractor = extractor
        self._pause_event = threading.Event()
        self._cancelled = threading.Event()

    # ------------------------------------------------------------------
    def pause(self) -> None:
        self._pause_event.set()
        self.sig_log.emit("warn", "任务已暂停")

    def resume(self) -> None:
        self._pause_event.clear()
        self.sig_log.emit("info", "任务已继续")

    def cancel(self) -> None:
        self._cancelled.set()
        self._pause_event.clear()  # 让暂停中的任务能走到 checkpoint 并退出
        self.sig_log.emit("warn", "正在取消任务…")

    @property
    def is_paused(self) -> bool:
        return self._pause_event.is_set()

    # ------------------------------------------------------------------
    def _checkpoint(self, _frame_index: int) -> None:
        if self._cancelled.is_set():
            raise ExtractCanceled()
        while self._pause_event.is_set():
            if self._cancelled.is_set():
                raise ExtractCanceled()
            self._pause_event.wait(0.05)

    def _on_progress(self, info: ProgressInfo) -> None:
        self.sig_progress.emit(
            info.video_path, info.frame_index, info.total_frames,
            info.saved, info.percent,
        )

    def run(self) -> None:  # noqa: D102 - Qt 线程入口
        started = time.monotonic()
        total_saved = 0
        canceled = False
        total = len(self.tasks)

        for idx, path in enumerate(self.tasks, start=1):
            if self._cancelled.is_set():
                canceled = True
                break

            name = os.path.basename(path)
            self.sig_file_start.emit(path, idx, total)
            self.sig_log.emit("info", f"开始处理 [{idx}/{total}] {name}")

            result: ExtractResult = self.extractor.extract(
                path, self.config,
                checkpoint=self._checkpoint,
                on_progress=self._on_progress,
            )
            total_saved += result.saved

            if result.error == "已取消":
                canceled = True
                self.sig_file_done.emit(path, result.saved, result.skipped, result.elapsed, "已取消")
                self.sig_log.emit("warn", f"已取消 {name}")
                break

            if result.ok:
                msg = f"完成 {name}：导出 {result.saved} 张"
                if result.skipped:
                    msg += f"，跳过 {result.skipped} 张（已存在）"
                self.sig_log.emit("success", msg)
            else:
                self.sig_log.emit("error", f"失败 {name}：{result.error}")
            self.sig_file_done.emit(
                path, result.saved, result.skipped, result.elapsed, result.error,
            )

        if canceled:
            self.sig_log.emit("warn", "任务已终止")
        else:
            self.sig_log.emit("success", f"全部完成，共导出 {total_saved} 张图片")
        self.sig_all_done.emit(total_saved, time.monotonic() - started, canceled)
