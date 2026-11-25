"""「图片转 GIF」标签页：Mixin 形式挂到 MainWindow 上。"""
from __future__ import annotations

import os
from datetime import datetime

from PySide6.QtCore import Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QPlainTextEdit, QProgressBar, QPushButton,
    QScrollArea, QSlider, QSpinBox, QVBoxLayout, QWidget,
)

from app.core.gif_maker import GifConfig, GifMaker
from app.core.utils import format_count, format_size, scan_images
from app.workers.gif_worker import GifWorker
from .theme import log_html


class ImageDropList(QListWidget):
    """可拖入图片/文件夹的图片列表。"""

    sig_paths_dropped = Signal(list)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setSelectionMode(QListWidget.ExtendedSelection)
        self.setObjectName("imageList")

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:  # noqa: N802
        if not event.mimeData().hasUrls():
            return super().dropEvent(event)
        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        if paths:
            self.sig_paths_dropped.emit(paths)
        event.acceptProposedAction()


class GifPageMixin:
    """依赖宿主 MainWindow 的 _header_card / _log / settings 等能力。"""

    # ------------------------------------------------------------------
    def _build_gif_page(self) -> QWidget:
        self.gif_maker = GifMaker()
        self.gif_worker: GifWorker | None = None
        self._gif_pixmap: QPixmap | None = None
        self._gif_preview_timer = QTimer(self)
        self._gif_preview_timer.setSingleShot(True)
        self._gif_preview_timer.timeout.connect(self._gif_show_preview)

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(12)

        from PySide6.QtWidgets import QSplitter

        splitter = QSplitter(Qt.Horizontal)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        left = self._build_gif_left()
        left.setMinimumWidth(390)
        splitter.addWidget(left)
        splitter.addWidget(self._build_gif_right())
        splitter.setSizes([430, 850])
        layout.addWidget(splitter, 1)
        return page

    def _build_gif_left(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")
        content = QWidget()
        box = QVBoxLayout(content)
        box.setContentsMargins(0, 0, 6, 0)
        box.setSpacing(12)
        scroll.setWidget(content)

        # 图片来源
        card, card_layout = self._header_card("图片来源", "按列表顺序合成动画；可拖拽图片或文件夹")
        row1 = QHBoxLayout()
        row1.setSpacing(8)
        self.gif_add_btn = QPushButton("＋ 添加图片")
        self.gif_add_folder_btn = QPushButton("＋ 添加文件夹")
        self.gif_remove_btn = QPushButton("移除选中")
        for b in (self.gif_add_btn, self.gif_add_folder_btn, self.gif_remove_btn):
            b.setMinimumHeight(34)
            row1.addWidget(b)
        card_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(8)
        self.gif_up_btn = QPushButton("↑ 上移")
        self.gif_down_btn = QPushButton("↓ 下移")
        self.gif_clear_btn = QPushButton("清空列表")
        for b in (self.gif_up_btn, self.gif_down_btn, self.gif_clear_btn):
            b.setMinimumHeight(30)
            row2.addWidget(b)
        card_layout.addLayout(row2)

        self.gif_list = ImageDropList()
        self.gif_list.setMinimumHeight(160)
        self.gif_list.sig_paths_dropped.connect(self._gif_add_dropped)
        self.gif_list.itemSelectionChanged.connect(self._gif_on_selection_changed)
        card_layout.addWidget(self.gif_list, 1)
        self.gif_source_card = card
        box.addWidget(card, 1)

        # 输出文件
        out_card, out_layout = self._header_card("保存为", "留空时默认保存到第一张图片所在目录")
        out_row = QHBoxLayout()
        out_row.setSpacing(8)
        self.gif_output_edit = QLineEdit()
        self.gif_output_edit.setPlaceholderText("例如：D:\\图片\\动画.gif")
        self.gif_browse_btn = QPushButton("浏览…")
        self.gif_browse_btn.setMinimumHeight(34)
        out_row.addWidget(self.gif_output_edit, 1)
        out_row.addWidget(self.gif_browse_btn)
        out_layout.addLayout(out_row)
        self.gif_output_card = out_card
        box.addWidget(out_card)

        # 参数
        opt_card, opt_layout = self._header_card("GIF 参数")
        form = QVBoxLayout()
        form.setSpacing(9)

        line1 = QHBoxLayout()
        line1.setSpacing(10)
        delay_label = QLabel("每帧间隔")
        delay_label.setObjectName("fieldLabel")
        self.gif_delay_spin = QSpinBox()
        self.gif_delay_spin.setRange(20, 10000)
        self.gif_delay_spin.setValue(100)
        self.gif_delay_spin.setSuffix(" ms")
        loop_label = QLabel("循环次数")
        loop_label.setObjectName("fieldLabel")
        self.gif_loop_spin = QSpinBox()
        self.gif_loop_spin.setRange(0, 10000)
        self.gif_loop_spin.setSpecialValueText("无限循环")
        self.gif_loop_spin.setValue(0)
        line1.addWidget(delay_label)
        line1.addWidget(self.gif_delay_spin)
        line1.addStretch(1)
        line1.addWidget(loop_label)
        line1.addWidget(self.gif_loop_spin)
        form.addLayout(line1)

        line2 = QHBoxLayout()
        line2.setSpacing(10)
        resize_label = QLabel("缩放方式")
        resize_label.setObjectName("fieldLabel")
        self.gif_resize_combo = QComboBox()
        self.gif_resize_combo.addItem("原始尺寸", "original")
        self.gif_resize_combo.addItem("指定宽度", "width")
        self.gif_resize_combo.addItem("指定高度", "height")
        self.gif_resize_combo.addItem("按比例缩放", "scale")
        self.gif_resize_value = QSpinBox()
        self.gif_resize_value.setRange(1, 10000)
        self.gif_resize_value.setValue(100)
        self.gif_resize_value.setEnabled(False)
        line2.addWidget(resize_label)
        line2.addWidget(self.gif_resize_combo, 1)
        line2.addWidget(self.gif_resize_value)
        form.addLayout(line2)
        self.gif_resize_combo.currentIndexChanged.connect(self._gif_on_resize_changed)

        self.gif_reverse_check = QCheckBox("倒序播放")
        self.gif_optimize_check = QCheckBox("优化体积（推荐，生成稍慢）")
        self.gif_optimize_check.setChecked(True)
        form.addWidget(self.gif_reverse_check)
        form.addWidget(self.gif_optimize_check)
        opt_layout.addLayout(form)
        self.gif_options_card = opt_card
        box.addWidget(opt_card)

        layout.addWidget(scroll, 1)

        self.gif_add_btn.clicked.connect(self._gif_select_files)
        self.gif_add_folder_btn.clicked.connect(self._gif_select_folder)
        self.gif_remove_btn.clicked.connect(self._gif_remove_selected)
        self.gif_up_btn.clicked.connect(lambda: self._gif_move(-1))
        self.gif_down_btn.clicked.connect(lambda: self._gif_move(1))
        self.gif_clear_btn.clicked.connect(self._gif_clear)
        self.gif_browse_btn.clicked.connect(self._gif_select_output)
        return panel

    def _build_gif_right(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        preview_card, preview_layout = self._header_card("图片预览", "拖动滑块按列表顺序查看")
        self.gif_preview_label = QLabel("添加图片后可在这里预览")
        self.gif_preview_label.setObjectName("previewBox")
        self.gif_preview_label.setAlignment(Qt.AlignCenter)
        self.gif_preview_label.setMinimumHeight(160)
        preview_layout.addWidget(self.gif_preview_label, 1)
        self.gif_slider = QSlider(Qt.Horizontal)
        self.gif_slider.setRange(0, 0)
        self.gif_slider.setEnabled(False)
        self.gif_slider.valueChanged.connect(lambda _v: self._gif_preview_timer.start(60))
        preview_layout.addWidget(self.gif_slider)
        self.gif_preview_meta = QLabel("尚未添加图片")
        self.gif_preview_meta.setObjectName("previewMeta")
        preview_layout.addWidget(self.gif_preview_meta)
        layout.addWidget(preview_card, 3)

        progress_card, progress_layout = self._header_card("生成进度")
        self.gif_current_label = QLabel("当前任务：—")
        self.gif_current_label.setObjectName("previewMeta")
        progress_layout.addWidget(self.gif_current_label)
        self.gif_progress = QProgressBar()
        self.gif_progress.setValue(0)
        progress_layout.addWidget(self.gif_progress)

        stat_row = QHBoxLayout()
        stat_row.setSpacing(16)
        self.gif_stat_frames = QLabel("已处理 0 张")
        self.gif_stat_size = QLabel("文件大小 —")
        for w in (self.gif_stat_frames, self.gif_stat_size):
            w.setObjectName("previewMeta")
            stat_row.addWidget(w)
        stat_row.addStretch(1)
        progress_layout.addLayout(stat_row)

        action_row = QHBoxLayout()
        action_row.setSpacing(10)
        self.gif_start_btn = QPushButton("生成 GIF")
        self.gif_start_btn.setObjectName("primary")
        self.gif_start_btn.setMinimumHeight(42)
        self.gif_pause_btn = QPushButton("暂停")
        self.gif_pause_btn.setObjectName("warning")
        self.gif_pause_btn.setEnabled(False)
        self.gif_cancel_btn = QPushButton("取消")
        self.gif_cancel_btn.setObjectName("danger")
        self.gif_cancel_btn.setEnabled(False)
        action_row.addWidget(self.gif_start_btn, 2)
        action_row.addWidget(self.gif_pause_btn, 1)
        action_row.addWidget(self.gif_cancel_btn, 1)
        progress_layout.addLayout(action_row)
        layout.addWidget(progress_card, 2)

        log_card, log_layout = self._header_card("运行日志")
        self.gif_log_box = QPlainTextEdit()
        self.gif_log_box.setObjectName("logBox")
        self.gif_log_box.setReadOnly(True)
        self.gif_log_box.setMaximumBlockCount(600)
        log_layout.addWidget(self.gif_log_box, 1)
        clear_row = QHBoxLayout()
        clear_row.addStretch(1)
        self.gif_open_btn = QPushButton("打开 GIF 所在目录")
        self.gif_clear_log_btn = QPushButton("清空日志")
        clear_row.addWidget(self.gif_open_btn)
        clear_row.addWidget(self.gif_clear_log_btn)
        log_layout.addLayout(clear_row)
        layout.addWidget(log_card, 2)

        self.gif_start_btn.clicked.connect(self._gif_start)
        self.gif_pause_btn.clicked.connect(self._gif_toggle_pause)
        self.gif_cancel_btn.clicked.connect(self._gif_cancel)
        self.gif_open_btn.clicked.connect(self._gif_open_output)
        self.gif_clear_log_btn.clicked.connect(self.gif_log_box.clear)
        return panel

    # ------------------------------------------------------------------
    # 图片列表
    # ------------------------------------------------------------------
    def _gif_select_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "选择图片", "",
            "图片文件 (*.jpg *.jpeg *.png *.webp *.bmp *.gif *.tif *.tiff);;所有文件 (*.*)",
        )
        if paths:
            self._gif_add_paths(paths)

    def _gif_select_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "选择包含图片的文件夹")
        if not folder:
            return
        images = scan_images([folder])
        if images:
            self._gif_add_paths(images)
        else:
            self._gif_log("warn", f"文件夹中没有找到图片：{folder}")

    def _gif_select_output(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "选择 GIF 保存文件夹", os.path.dirname(self.gif_output_edit.text()))
        if folder:
            name = os.path.basename(self.gif_output_edit.text()) or "animation.gif"
            if not name.lower().endswith(".gif"):
                name += ".gif"
            self.gif_output_edit.setText(os.path.join(folder, name))

    def _gif_add_dropped(self, paths: list) -> None:
        self._gif_add_paths(scan_images(paths))

    def _gif_add_paths(self, paths: list) -> None:
        existing = {
            self.gif_list.item(i).data(Qt.UserRole)
            for i in range(self.gif_list.count())
        }
        added = 0
        for path in paths:
            norm = os.path.normpath(path)
            if norm in existing or not os.path.isfile(norm):
                continue
            item = QListWidgetItem(os.path.basename(norm))
            item.setData(Qt.UserRole, norm)
            item.setToolTip(norm)
            self.gif_list.addItem(item)
            existing.add(norm)
            added += 1
        if added:
            self._gif_log("info", f"已添加 {added} 张图片")
            self._gif_update_slider()
            if self.gif_list.currentRow() < 0:
                self.gif_list.setCurrentRow(0)
        else:
            self._gif_log("warn", "没有新增图片（可能重复或文件不存在）")

    def _gif_remove_selected(self) -> None:
        rows = sorted({self.gif_list.row(item) for item in self.gif_list.selectedItems()}, reverse=True)
        for row in rows:
            self.gif_list.takeItem(row)
        if rows:
            self._gif_log("info", f"已移除 {len(rows)} 张图片")
            self._gif_update_slider()
            self._gif_on_selection_changed()

    def _gif_move(self, delta: int) -> None:
        item = self.gif_list.currentItem()
        if not item:
            return
        row = self.gif_list.row(item)
        target = row + delta
        if target < 0 or target >= self.gif_list.count():
            return
        taken = self.gif_list.takeItem(row)
        self.gif_list.insertItem(target, taken)
        self.gif_list.setCurrentRow(target)
        self._gif_log("info", "已调整图片顺序")

    def _gif_clear(self) -> None:
        self.gif_list.clear()
        self._gif_update_slider()
        self._gif_on_selection_changed()
        self._gif_log("info", "已清空图片列表")

    def _gif_update_slider(self) -> None:
        count = self.gif_list.count()
        self.gif_slider.setRange(0, max(0, count - 1))
        self.gif_slider.setEnabled(count > 0)
        self.gif_preview_meta.setText(f"共 {count} 张图片" if count else "尚未添加图片")

    def _gif_on_selection_changed(self) -> None:
        item = self.gif_list.currentItem()
        if item:
            row = self.gif_list.row(item)
            self.gif_slider.setValue(row)
            self._gif_show_preview()

    def _gif_show_preview(self) -> None:
        item = self.gif_list.item(self.gif_slider.value())
        if not item:
            self._gif_pixmap = None
            self.gif_preview_label.setText("添加图片后可在这里预览")
            return
        path = item.data(Qt.UserRole)
        pixmap = QPixmap(path)
        if pixmap.isNull():
            self._gif_log("error", f"无法读取图片：{path}")
            return
        self._gif_pixmap = pixmap
        self._gif_render_preview()

    def _gif_render_preview(self) -> None:
        pixmap = getattr(self, "_gif_pixmap", None)
        if not pixmap or pixmap.isNull():
            return
        size = self.gif_preview_label.size()
        scaled = pixmap.scaled(
            max(100, size.width() - 12), max(80, size.height() - 12),
            Qt.KeepAspectRatio, Qt.SmoothTransformation,
        )
        self.gif_preview_label.setPixmap(scaled)

    def _gif_resize_surface(self) -> None:
        self._gif_render_preview()

    # ------------------------------------------------------------------
    # 参数与流程
    # ------------------------------------------------------------------
    def _gif_on_resize_changed(self) -> None:
        mode = self.gif_resize_combo.currentData()
        enabled = mode != "original"
        self.gif_resize_value.setEnabled(enabled)
        if enabled:
            self.gif_resize_value.setSuffix(" px" if mode in ("width", "height") else " %")
            self.gif_resize_value.setValue(480 if mode == "width" else (100 if mode == "scale" else 480))

    def _gif_collect_config(self) -> GifConfig:
        return GifConfig(
            output_path=self.gif_output_edit.text().strip(),
            delay_ms=self.gif_delay_spin.value(),
            loop=self.gif_loop_spin.value(),
            resize_mode=self.gif_resize_combo.currentData(),
            resize_value=self.gif_resize_value.value(),
            reverse=self.gif_reverse_check.isChecked(),
            optimize=self.gif_optimize_check.isChecked(),
        )

    def _gif_load_settings(self) -> None:
        s = self.settings
        self.gif_output_edit.setText(s.value("gif_output", "", str))
        self.gif_delay_spin.setValue(int(s.value("gif_delay", 100, int)))
        self.gif_loop_spin.setValue(int(s.value("gif_loop", 0, int)))
        idx = self.gif_resize_combo.findData(s.value("gif_resize_mode", "original", str))
        if idx >= 0:
            self.gif_resize_combo.setCurrentIndex(idx)
        self.gif_resize_value.setValue(int(s.value("gif_resize_value", 100, int)))
        self.gif_reverse_check.setChecked(s.value("gif_reverse", False, bool))
        self.gif_optimize_check.setChecked(s.value("gif_optimize", True, bool))
        self._gif_on_resize_changed()

    def _gif_save_settings(self) -> None:
        cfg = self._gif_collect_config()
        s = self.settings
        s.setValue("gif_output", cfg.output_path)
        s.setValue("gif_delay", cfg.delay_ms)
        s.setValue("gif_loop", cfg.loop)
        s.setValue("gif_resize_mode", cfg.resize_mode)
        s.setValue("gif_resize_value", cfg.resize_value)
        s.setValue("gif_reverse", cfg.reverse)
        s.setValue("gif_optimize", cfg.optimize)

    def _gif_start(self) -> None:
        if self.gif_worker and self.gif_worker.isRunning():
            return
        images = [
            self.gif_list.item(i).data(Qt.UserRole)
            for i in range(self.gif_list.count())
        ]
        if len(images) < 2:
            self._gif_log("warn", "请至少添加 2 张图片")
            return
        missing = [p for p in images if not os.path.isfile(p)]
        if missing:
            self._gif_log("error", f"有 {len(missing)} 张图片不存在，请先移除")
            return

        out_path = self.gif_output_edit.text().strip()
        if not out_path:
            out_path = os.path.join(os.path.dirname(images[0]), "animation.gif")
            self.gif_output_edit.setText(out_path)
        if not out_path.lower().endswith(".gif"):
            out_path += ".gif"
            self.gif_output_edit.setText(out_path)
        try:
            os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        except OSError as exc:
            self._gif_log("error", f"无法创建保存目录：{exc}")
            return

        cfg = self._gif_collect_config()
        cfg.output_path = out_path
        self.gif_progress.setValue(0)
        self.gif_stat_frames.setText("已处理 0 张")
        self.gif_stat_size.setText("文件大小 —")
        self.gif_current_label.setText(f"当前任务：合成 {len(images)} 张图片")

        self.gif_worker = GifWorker(images, cfg, self.gif_maker, self)
        self.gif_worker.sig_progress.connect(self._gif_on_progress)
        self.gif_worker.sig_log.connect(self._gif_log)
        self.gif_worker.sig_done.connect(self._gif_on_done)
        self.gif_worker.finished.connect(self._gif_on_finished)
        self.gif_worker.start()

        self.gif_start_btn.setEnabled(False)
        self.gif_pause_btn.setEnabled(True)
        self.gif_pause_btn.setText("暂停")
        self.gif_cancel_btn.setEnabled(True)
        self.gif_source_card.setEnabled(False)
        self.gif_output_card.setEnabled(False)
        self.gif_options_card.setEnabled(False)
        self.statusBar().showMessage("正在生成 GIF…")

    def _gif_toggle_pause(self) -> None:
        if not self.gif_worker or not self.gif_worker.isRunning():
            return
        if self.gif_worker.is_paused:
            self.gif_worker.resume()
            self.gif_pause_btn.setText("暂停")
        else:
            self.gif_worker.pause()
            self.gif_pause_btn.setText("继续")

    def _gif_cancel(self) -> None:
        if self.gif_worker and self.gif_worker.isRunning():
            self.gif_worker.cancel()
            self.gif_cancel_btn.setEnabled(False)

    def _gif_on_progress(self, index: int, total: int, percent: float) -> None:
        self.gif_progress.setValue(int(percent))
        self.gif_stat_frames.setText(f"已处理 {format_count(index)} / {format_count(total)} 张")

    def _gif_on_done(self, frames: int, size: int, elapsed: float, canceled: bool) -> None:
        if not canceled:
            self.gif_progress.setValue(100)
            self.gif_stat_size.setText(f"文件大小 {format_size(size)} · 用时 {elapsed:.1f} 秒")
            prefix = "完成 · "
        else:
            prefix = "已取消 · "
        self.statusBar().showMessage(f"{prefix}GIF 共 {format_count(frames)} 帧")
        self.gif_start_btn.setEnabled(True)
        self.gif_pause_btn.setEnabled(False)
        self.gif_cancel_btn.setEnabled(False)
        self.gif_pause_btn.setText("暂停")
        self.gif_source_card.setEnabled(True)
        self.gif_output_card.setEnabled(True)
        self.gif_options_card.setEnabled(True)

    def _gif_on_finished(self) -> None:
        if self.gif_worker:
            self.gif_worker.deleteLater()
            self.gif_worker = None

    def _gif_open_output(self) -> None:
        path = self.gif_output_edit.text().strip()
        folder = os.path.dirname(path) if path else ""
        if folder and os.path.isdir(folder):
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))
        else:
            self._gif_log("warn", "输出目录尚不存在")

    def _gif_log(self, level: str, message: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        self.gif_log_box.appendHtml(f'<span style="color:#9AA3B2">{stamp}</span> ' + log_html(level, message))
