"""主窗口：选择视频 → 配置参数 → 后台导出 → 进度与日志。"""
from __future__ import annotations

import os
from datetime import datetime
from typing import List

import cv2
from PySide6.QtCore import QSettings, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QIcon, QImage, QPixmap
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFrame, QGridLayout,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMainWindow, QPlainTextEdit, QProgressBar, QPushButton, QScrollArea,
    QSlider, QSpinBox, QSplitter, QTabWidget, QVBoxLayout, QWidget,
)

from app.core.config import ExtractConfig
from app.core.extractor import FrameExtractor, probe_video
from app.core.utils import format_count, format_duration, format_size, scan_videos
from app.workers.extract_worker import ExtractWorker
from .about_page import create_about_widget
from .gif_page import GifPageMixin
from .theme import APP_QSS, log_html

# 二维码放在项目资源目录里，相对路径引用，换机器/打包后依然可用
_ASSETS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "app", "assets",
)
_ABOUT_QR = os.path.join(_ASSETS_DIR, "wechat_qr.jpg")
_ICON_PATH = os.path.join(_ASSETS_DIR, "app_icon.ico")


class VideoDropList(QListWidget):
    """支持从资源管理器拖入视频 / 文件夹的列表。"""

    sig_paths_dropped = Signal(list)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setSelectionMode(QListWidget.ExtendedSelection)
        self.setObjectName("videoList")

    def dragEnterEvent(self, event) -> None:  # noqa: N802 - Qt 命名
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


class MainWindow(GifPageMixin, QMainWindow):
    APP_NAME = "帧影 FrameFlow"

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{self.APP_NAME} · 视频逐帧导出工具")
        self.setMinimumSize(1060, 700)
        self.resize(1320, 860)
        self.setStyleSheet(APP_QSS)
        self.setWindowIcon(QIcon(_ICON_PATH))

        self.settings = QSettings("FrameFlow", "VideoFrameExtractor")
        self.extractor = FrameExtractor()
        self.worker: ExtractWorker | None = None

        # 预览相关状态
        self._preview_cap: cv2.VideoCapture | None = None
        self._preview_frames = 0
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.timeout.connect(self._seek_preview)

        # 任务统计
        self._file_total = 0
        self._done_count = 0
        self._base_saved = 0
        self._base_skipped = 0

        self._build_ui()
        self._load_settings()
        self.statusBar().showMessage("就绪 · 可拖拽视频或文件夹到左侧列表")

    # ==================================================================
    # 界面构建
    # ==================================================================
    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(20, 14, 20, 10)
        root.setSpacing(12)

        root.addWidget(self._build_header())

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_extract_page(), "视频抽帧")
        self.tabs.addTab(self._build_gif_page(), "图片转 GIF")
        self.tabs.addTab(self._build_about_page(), "关于")
        root.addWidget(self.tabs, 1)

    def _build_about_page(self) -> QWidget:
        return create_about_widget(
            app_name=self.APP_NAME,
            version="1.1",
            description="视频逐帧导出 · 图片合成 GIF\n批量处理、参数可控、后续可持续扩展。",
            qr_path=_ABOUT_QR,
            icon_path=_ICON_PATH,
        )

    def _build_extract_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        left = self._build_left_panel()
        left.setMinimumWidth(390)
        splitter.addWidget(left)
        splitter.addWidget(self._build_right_panel())
        splitter.setSizes([430, 850])
        layout.addWidget(splitter, 1)
        return page

    def _header_card(self, title: str, hint: str = "") -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)
        title_label = QLabel(title)
        title_label.setObjectName("cardTitle")
        layout.addWidget(title_label)
        if hint:
            hint_label = QLabel(hint)
            hint_label.setObjectName("cardHint")
            layout.addWidget(hint_label)
        return card, layout

    def _build_header(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("header")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 10, 16, 10)

        title = QLabel(self.APP_NAME)
        title.setObjectName("appTitle")
        subtitle = QLabel("视频逐帧导出 · 图片合成 GIF · 批量、可控、可扩展")
        subtitle.setObjectName("appSubtitle")
        text_box = QVBoxLayout()
        text_box.setSpacing(1)
        text_box.addWidget(title)
        text_box.addWidget(subtitle)
        layout.addLayout(text_box)
        layout.addStretch(1)

        badge = QLabel("v1.1")
        badge.setObjectName("versionBadge")
        layout.addWidget(badge)
        return bar

    # ------------------------------------------------------------------
    def _build_left_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 6, 0)
        content_layout.setSpacing(12)
        scroll.setWidget(content)

        # ---- 视频来源 ----
        source_card, source_layout = self._header_card("视频来源", "支持拖拽；可多选文件或整个文件夹")
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self.add_file_btn = QPushButton("＋ 添加文件")
        self.add_folder_btn = QPushButton("＋ 添加文件夹")
        self.remove_btn = QPushButton("移除选中")
        for b in (self.add_file_btn, self.add_folder_btn, self.remove_btn):
            b.setMinimumHeight(34)
            btn_row.addWidget(b)
        source_layout.addLayout(btn_row)

        self.video_list = VideoDropList()
        self.video_list.setMinimumHeight(150)
        self.video_list.sig_paths_dropped.connect(self._add_dropped_paths)
        self.video_list.itemSelectionChanged.connect(self._on_selection_changed)
        source_layout.addWidget(self.video_list, 1)
        self.source_card = source_card
        content_layout.addWidget(source_card, 1)

        # ---- 输出目录 ----
        output_card, output_layout = self._header_card("保存位置")
        out_row = QHBoxLayout()
        out_row.setSpacing(8)
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("选择导出图片的文件夹（留空将自动创建）")
        self.output_browse_btn = QPushButton("浏览…")
        self.output_browse_btn.setMinimumHeight(34)
        out_row.addWidget(self.output_edit, 1)
        out_row.addWidget(self.output_browse_btn)
        output_layout.addLayout(out_row)

        self.subfolder_check = QCheckBox("每个视频单独建一个子文件夹（推荐）")
        self.subfolder_check.setChecked(True)
        output_layout.addWidget(self.subfolder_check)
        self.output_card = output_card
        content_layout.addWidget(output_card)

        # ---- 导出参数 ----
        options_card, options_layout = self._header_card("导出参数", "参数在开始导出时生效")
        form = QGridLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(9)
        form.setColumnStretch(1, 1)

        def label(text: str, row: int) -> None:
            w = QLabel(text)
            w.setObjectName("fieldLabel")
            form.addWidget(w, row, 0)

        # 格式 / 质量
        label("图片格式", 0)
        self.format_combo = QComboBox()
        self.format_combo.addItem("JPG（体积小）", "jpg")
        self.format_combo.addItem("PNG（无损）", "png")
        self.format_combo.addItem("WebP（兼顾）", "webp")
        form.addWidget(self.format_combo, 0, 1)

        label("图片质量", 1)
        self.quality_spin = QSpinBox()
        self.quality_spin.setRange(1, 100)
        self.quality_spin.setValue(95)
        self.quality_spin.setSuffix(" %")
        form.addWidget(self.quality_spin, 1, 1)

        # 缩放
        label("缩放方式", 2)
        self.resize_combo = QComboBox()
        self.resize_combo.addItem("原始尺寸", "original")
        self.resize_combo.addItem("指定宽度", "width")
        self.resize_combo.addItem("指定高度", "height")
        self.resize_combo.addItem("按比例缩放", "scale")
        form.addWidget(self.resize_combo, 2, 1)

        label("缩放数值", 3)
        self.resize_value_spin = QSpinBox()
        self.resize_value_spin.setRange(1, 10000)
        self.resize_value_spin.setValue(100)
        self.resize_value_spin.setEnabled(False)
        form.addWidget(self.resize_value_spin, 3, 1)
        self.resize_combo.currentIndexChanged.connect(self._on_resize_mode_changed)

        # 抽帧规则
        label("抽帧方式", 4)
        self.frame_mode_combo = QComboBox()
        self.frame_mode_combo.addItem("全部帧（每一帧都保存）", "all")
        self.frame_mode_combo.addItem("每隔 N 帧保存一张", "every_n")
        self.frame_mode_combo.addItem("每秒保存 N 张", "per_second")
        form.addWidget(self.frame_mode_combo, 4, 1)

        label("抽帧参数", 5)
        self.frame_value_spin = QSpinBox()
        self.frame_value_spin.setRange(1, 100000)
        self.frame_value_spin.setValue(1)
        self.frame_value_spin.setEnabled(False)
        form.addWidget(self.frame_value_spin, 5, 1)
        self.frame_mode_combo.currentIndexChanged.connect(self._on_frame_mode_changed)

        label("开始时间", 6)
        self.start_spin = QDoubleSpinBox()
        self.start_spin.setRange(0.0, 100000.0)
        self.start_spin.setDecimals(2)
        self.start_spin.setSuffix(" 秒")
        form.addWidget(self.start_spin, 6, 1)

        label("结束时间", 7)
        self.end_spin = QDoubleSpinBox()
        self.end_spin.setRange(0.0, 100000.0)
        self.end_spin.setDecimals(2)
        self.end_spin.setSuffix(" 秒（0 = 到结尾）")
        form.addWidget(self.end_spin, 7, 1)

        label("命名模板", 8)
        self.name_edit = QLineEdit("{name}_{index:06d}")
        form.addWidget(self.name_edit, 8, 1)

        label("最多保存", 9)
        self.max_spin = QSpinBox()
        self.max_spin.setRange(0, 10_000_000)
        self.max_spin.setSpecialValueText("不限制")
        form.addWidget(self.max_spin, 9, 1)

        options_layout.addLayout(form)
        self.overwrite_check = QCheckBox("覆盖同名图片（关闭时跳过已存在文件）")
        options_layout.addWidget(self.overwrite_check)
        hint = QLabel("命名变量：{name} 视频名 · {index} 序号 · {frame} 帧号 · {fps} 帧率")
        hint.setObjectName("cardHint")
        hint.setWordWrap(True)
        options_layout.addWidget(hint)
        self.options_card = options_card
        content_layout.addWidget(options_card)

        layout.addWidget(scroll, 1)
        return panel

    # ------------------------------------------------------------------
    def _build_right_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # ---- 预览 ----
        preview_card, preview_layout = self._header_card("帧预览", "拖动下方滑块查看视频任意位置")
        self.preview_label = QLabel("选择视频后可在这里预览画面")
        self.preview_label.setObjectName("previewBox")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumHeight(160)
        preview_layout.addWidget(self.preview_label, 1)

        self.preview_slider = QSlider(Qt.Horizontal)
        self.preview_slider.setRange(0, 1000)
        self.preview_slider.setValue(0)
        self.preview_slider.setEnabled(False)
        self.preview_slider.valueChanged.connect(self._on_preview_slider_changed)
        preview_layout.addWidget(self.preview_slider)
        self.preview_meta = QLabel("尚未加载视频")
        self.preview_meta.setObjectName("previewMeta")
        preview_layout.addWidget(self.preview_meta)
        layout.addWidget(preview_card, 3)

        # ---- 进度 ----
        progress_card, progress_layout = self._header_card("导出进度")
        self.current_file_label = QLabel("当前任务：—")
        self.current_file_label.setObjectName("previewMeta")
        progress_layout.addWidget(self.current_file_label)

        self.file_progress = QProgressBar()
        self.file_progress.setValue(0)
        progress_layout.addWidget(self.file_progress)

        self.overall_label = QLabel("总进度")
        self.overall_label.setObjectName("fieldLabel")
        progress_layout.addWidget(self.overall_label)
        self.overall_progress = QProgressBar()
        self.overall_progress.setObjectName("overall")
        self.overall_progress.setValue(0)
        progress_layout.addWidget(self.overall_progress)

        stat_row = QHBoxLayout()
        stat_row.setSpacing(16)
        self.stat_saved = QLabel("已导出 0 张")
        self.stat_skipped = QLabel("已跳过 0 张")
        self.stat_elapsed = QLabel("用时 0.0 秒")
        for w in (self.stat_saved, self.stat_skipped, self.stat_elapsed):
            w.setObjectName("previewMeta")
            stat_row.addWidget(w)
        stat_row.addStretch(1)
        progress_layout.addLayout(stat_row)

        action_row = QHBoxLayout()
        action_row.setSpacing(10)
        self.start_btn = QPushButton("开始导出")
        self.start_btn.setObjectName("primary")
        self.start_btn.setMinimumHeight(42)
        self.pause_btn = QPushButton("暂停")
        self.pause_btn.setObjectName("warning")
        self.pause_btn.setEnabled(False)
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setObjectName("danger")
        self.cancel_btn.setEnabled(False)
        action_row.addWidget(self.start_btn, 2)
        action_row.addWidget(self.pause_btn, 1)
        action_row.addWidget(self.cancel_btn, 1)
        progress_layout.addLayout(action_row)
        layout.addWidget(progress_card, 2)

        # ---- 日志 ----
        log_card, log_layout = self._header_card("运行日志")
        self.log_box = QPlainTextEdit()
        self.log_box.setObjectName("logBox")
        self.log_box.setReadOnly(True)
        self.log_box.setMaximumBlockCount(600)
        log_layout.addWidget(self.log_box, 1)
        clear_row = QHBoxLayout()
        clear_row.addStretch(1)
        self.open_output_btn = QPushButton("打开输出目录")
        self.clear_log_btn = QPushButton("清空日志")
        clear_row.addWidget(self.open_output_btn)
        clear_row.addWidget(self.clear_log_btn)
        log_layout.addLayout(clear_row)
        layout.addWidget(log_card, 2)

        # 信号连接
        self.add_file_btn.clicked.connect(self._select_files)
        self.add_folder_btn.clicked.connect(self._select_folder)
        self.remove_btn.clicked.connect(self._remove_selected)
        self.output_browse_btn.clicked.connect(self._select_output)
        self.start_btn.clicked.connect(self._start_extract)
        self.pause_btn.clicked.connect(self._toggle_pause)
        self.cancel_btn.clicked.connect(self._cancel_extract)
        self.open_output_btn.clicked.connect(self._open_output_dir)
        self.clear_log_btn.clicked.connect(self.log_box.clear)
        return panel

    # ==================================================================
    # 文件与预览
    # ==================================================================
    def _select_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "选择视频文件", "",
            "视频文件 (*.mp4 *.mkv *.avi *.mov *.wmv *.flv *.webm *.m4v *.mpg *.mpeg *.ts *.3gp);;所有文件 (*.*)",
        )
        if paths:
            self._add_paths(paths)

    def _select_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "选择包含视频的文件夹")
        if folder:
            videos = scan_videos([folder])
            if videos:
                self._add_paths(videos)
            else:
                self._log("warn", f"文件夹中没有找到视频：{folder}")

    def _select_output(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "选择图片保存文件夹", self.output_edit.text())
        if folder:
            self.output_edit.setText(folder)

    def _add_dropped_paths(self, paths: List[str]) -> None:
        self._add_paths(scan_videos(paths))

    def _add_paths(self, paths: List[str]) -> None:
        existing = {
            self.video_list.item(i).data(Qt.UserRole)
            for i in range(self.video_list.count())
        }
        added = 0
        for path in paths:
            norm = os.path.normpath(path)
            if norm in existing or not os.path.isfile(norm):
                continue
            item = QListWidgetItem(os.path.basename(norm))
            item.setData(Qt.UserRole, norm)
            item.setToolTip(norm)
            self.video_list.addItem(item)
            existing.add(norm)
            added += 1
        if added:
            self._log("info", f"已添加 {added} 个视频")
            if self.video_list.currentRow() < 0:
                self.video_list.setCurrentRow(0)
        else:
            self._log("warn", "没有新增视频（可能重复或文件不存在）")

    def _remove_selected(self) -> None:
        rows = sorted({self.video_list.row(item) for item in self.video_list.selectedItems()}, reverse=True)
        for row in rows:
            self.video_list.takeItem(row)
        if rows:
            self._log("info", f"已移除 {len(rows)} 个视频")
            self._on_selection_changed()

    def _on_selection_changed(self) -> None:
        item = self.video_list.currentItem()
        if not item:
            self._close_preview()
            return
        path = item.data(Qt.UserRole)
        try:
            info = probe_video(path)
        except Exception as exc:  # noqa: BLE001
            self._log("error", f"无法读取视频信息：{exc}")
            self._close_preview()
            return

        if self._preview_cap:
            self._preview_cap.release()
        self._preview_cap = cv2.VideoCapture(path)
        self._preview_frames = info.frame_count
        self.preview_slider.setEnabled(info.frame_count > 1)
        self.preview_slider.setValue(0)
        self.preview_meta.setText(
            f"{info.resolution} · {info.fps:.2f} fps · {format_duration(info.duration)} · "
            f"{format_count(info.frame_count)} 帧 · {format_size(os.path.getsize(path))}"
        )
        self._seek_preview()

    def _on_preview_slider_changed(self, _value: int) -> None:
        self._preview_timer.start(80)  # 防抖，避免拖动时疯狂解码

    def _seek_preview(self) -> None:
        cap = self._preview_cap
        if not cap or not cap.isOpened():
            return
        ratio = self.preview_slider.value() / 1000.0
        target = int(ratio * max(0, self._preview_frames - 1))
        cap.set(cv2.CAP_PROP_POS_FRAMES, target)
        ok, frame = cap.read()
        if not ok:
            return
        image = QImage(
            frame.data, frame.shape[1], frame.shape[0], frame.strides[0],
            QImage.Format.Format_BGR888,
        )
        self._preview_pixmap = QPixmap.fromImage(image)
        self._render_preview()

    def _render_preview(self) -> None:
        pixmap = getattr(self, "_preview_pixmap", None)
        if pixmap is None or pixmap.isNull():
            return
        size = self.preview_label.size()
        scaled = pixmap.scaled(
            max(100, size.width() - 12), max(80, size.height() - 12),
            Qt.KeepAspectRatio, Qt.SmoothTransformation,
        )
        self.preview_label.setPixmap(scaled)

    def _close_preview(self) -> None:
        if self._preview_cap:
            self._preview_cap.release()
        self._preview_cap = None
        self._preview_pixmap = None
        self.preview_label.setText("选择视频后可在这里预览画面")
        self.preview_meta.setText("尚未加载视频")
        self.preview_slider.setEnabled(False)

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt 命名
        super().resizeEvent(event)
        QTimer.singleShot(0, self._render_preview)
        QTimer.singleShot(0, self._gif_resize_surface)

    # ==================================================================
    # 参数联动与设置持久化
    # ==================================================================
    def _on_resize_mode_changed(self) -> None:
        mode = self.resize_combo.currentData()
        enabled = mode != "original"
        self.resize_value_spin.setEnabled(enabled)
        if enabled:
            self.resize_value_spin.setSuffix(" px" if mode in ("width", "height") else " %")
            self.resize_value_spin.setValue(1080 if mode == "width" else (100 if mode == "scale" else 720))

    def _on_frame_mode_changed(self) -> None:
        mode = self.frame_mode_combo.currentData()
        enabled = mode != "all"
        self.frame_value_spin.setEnabled(enabled)
        if enabled:
            self.frame_value_spin.setValue(5 if mode == "every_n" else 2)

    def _collect_config(self) -> ExtractConfig:
        return ExtractConfig(
            output_dir=self.output_edit.text().strip(),
            image_format=self.format_combo.currentData(),
            quality=self.quality_spin.value(),
            resize_mode=self.resize_combo.currentData(),
            resize_value=self.resize_value_spin.value(),
            frame_mode=self.frame_mode_combo.currentData(),
            frame_value=self.frame_value_spin.value(),
            start_time=self.start_spin.value(),
            end_time=self.end_spin.value(),
            subfolder_per_video=self.subfolder_check.isChecked(),
            name_pattern=self.name_edit.text().strip(),
            overwrite=self.overwrite_check.isChecked(),
            max_frames=self.max_spin.value(),
        )

    def _load_settings(self) -> None:
        s = self.settings
        self.output_edit.setText(s.value("output_dir", "", str))
        self._set_combo(self.format_combo, s.value("format", "jpg", str))
        self.quality_spin.setValue(int(s.value("quality", 95, int)))
        self._set_combo(self.resize_combo, s.value("resize_mode", "original", str))
        self.resize_value_spin.setValue(int(s.value("resize_value", 100, int)))
        self._set_combo(self.frame_mode_combo, s.value("frame_mode", "all", str))
        self.frame_value_spin.setValue(int(s.value("frame_value", 1, int)))
        self.start_spin.setValue(float(s.value("start_time", 0.0, float)))
        self.end_spin.setValue(float(s.value("end_time", 0.0, float)))
        self.subfolder_check.setChecked(s.value("subfolder", True, bool))
        self.name_edit.setText(s.value("name_pattern", "{name}_{index:06d}", str))
        self.overwrite_check.setChecked(s.value("overwrite", False, bool))
        self.max_spin.setValue(int(s.value("max_frames", 0, int)))
        self._on_resize_mode_changed()
        self._on_frame_mode_changed()
        self._gif_load_settings()

    def _save_settings(self) -> None:
        cfg = self._collect_config()
        s = self.settings
        s.setValue("output_dir", cfg.output_dir)
        s.setValue("format", cfg.image_format)
        s.setValue("quality", cfg.quality)
        s.setValue("resize_mode", cfg.resize_mode)
        s.setValue("resize_value", cfg.resize_value)
        s.setValue("frame_mode", cfg.frame_mode)
        s.setValue("frame_value", cfg.frame_value)
        s.setValue("start_time", cfg.start_time)
        s.setValue("end_time", cfg.end_time)
        s.setValue("subfolder", cfg.subfolder_per_video)
        s.setValue("name_pattern", cfg.name_pattern)
        s.setValue("overwrite", cfg.overwrite)
        s.setValue("max_frames", cfg.max_frames)
        self._gif_save_settings()

    @staticmethod
    def _set_combo(combo: QComboBox, value: str) -> None:
        idx = combo.findData(value)
        if idx >= 0:
            combo.setCurrentIndex(idx)

    # ==================================================================
    # 导出流程
    # ==================================================================
    def _start_extract(self) -> None:
        if self.worker and self.worker.isRunning():
            return
        tasks = [
            self.video_list.item(i).data(Qt.UserRole)
            for i in range(self.video_list.count())
        ]
        if not tasks:
            self._log("warn", "请先添加至少一个视频")
            self.statusBar().showMessage("请先添加视频")
            return

        out_dir = self.output_edit.text().strip()
        if not out_dir:
            out_dir = os.path.join(os.path.dirname(tasks[0]), "frames_export")
            self.output_edit.setText(out_dir)
            self._log("warn", f"未指定保存位置，已自动使用：{out_dir}")
        try:
            os.makedirs(out_dir, exist_ok=True)
        except OSError as exc:
            self._log("error", f"无法创建输出目录：{exc}")
            return

        cfg = self._collect_config()
        cfg.output_dir = out_dir
        self._file_total = len(tasks)
        self._done_count = 0
        self._base_saved = 0
        self._base_skipped = 0
        self.file_progress.setValue(0)
        self.overall_progress.setValue(0)
        self.stat_saved.setText("已导出 0 张")
        self.stat_skipped.setText("已跳过 0 张")
        self.stat_elapsed.setText("用时 0.0 秒")
        self.current_file_label.setText(f"当前任务：1 / {len(tasks)}")

        self.worker = ExtractWorker(tasks, cfg, self.extractor, self)
        self.worker.sig_file_start.connect(self._on_file_start)
        self.worker.sig_progress.connect(self._on_progress)
        self.worker.sig_file_done.connect(self._on_file_done)
        self.worker.sig_log.connect(self._log)
        self.worker.sig_all_done.connect(self._on_all_done)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.start()

        self.start_btn.setEnabled(False)
        self.pause_btn.setEnabled(True)
        self.pause_btn.setText("暂停")
        self.cancel_btn.setEnabled(True)
        self.source_card.setEnabled(False)
        self.output_card.setEnabled(False)
        self.options_card.setEnabled(False)
        self.statusBar().showMessage("正在导出…")

    def _toggle_pause(self) -> None:
        if not self.worker or not self.worker.isRunning():
            return
        if self.worker.is_paused:
            self.worker.resume()
            self.pause_btn.setText("暂停")
        else:
            self.worker.pause()
            self.pause_btn.setText("继续")
            self.statusBar().showMessage("任务已暂停")

    def _cancel_extract(self) -> None:
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.cancel_btn.setEnabled(False)

    def _on_file_start(self, path: str, index: int, total: int) -> None:
        self._file_total = total
        self.current_file_label.setText(f"当前任务 [{index}/{total}]：{os.path.basename(path)}")
        self.file_progress.setValue(0)

    def _on_progress(self, _path: str, _frame: int, _total: int, saved: int, percent: float) -> None:
        self.file_progress.setValue(int(percent))
        self.stat_saved.setText(f"已导出 {format_count(self._base_saved + saved)} 张")
        overall = (self._done_count + percent / 100.0) / max(1, self._file_total) * 100.0
        self.overall_progress.setValue(int(min(100.0, overall)))

    def _on_file_done(self, _path: str, saved: int, skipped: int, _elapsed: float, _error: str) -> None:
        self._done_count += 1
        self._base_saved += saved
        self._base_skipped += skipped
        self.stat_saved.setText(f"已导出 {format_count(self._base_saved)} 张")
        self.stat_skipped.setText(f"已跳过 {format_count(self._base_skipped)} 张")
        self.file_progress.setValue(100)

    def _on_all_done(self, saved: int, elapsed: float, canceled: bool) -> None:
        self.overall_progress.setValue(100 if not canceled else self.overall_progress.value())
        self.stat_elapsed.setText(f"用时 {elapsed:.1f} 秒")
        prefix = "已取消 · " if canceled else "完成 · "
        self.statusBar().showMessage(f"{prefix}共导出 {format_count(saved)} 张图片")
        self.start_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        self.pause_btn.setText("暂停")
        self.source_card.setEnabled(True)
        self.output_card.setEnabled(True)
        self.options_card.setEnabled(True)

    def _on_worker_finished(self) -> None:
        if self.worker:
            self.worker.deleteLater()
            self.worker = None

    def _open_output_dir(self) -> None:
        path = self.output_edit.text().strip()
        if path and os.path.isdir(path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        else:
            self._log("warn", "输出目录尚不存在")

    # ==================================================================
    def _log(self, level: str, message: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        self.log_box.appendHtml(f'<span style="color:#9AA3B2">{stamp}</span> ' + log_html(level, message))

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt 命名
        self._save_settings()
        if self._preview_cap:
            self._preview_cap.release()
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait(3000)
        if self.gif_worker and self.gif_worker.isRunning():
            self.gif_worker.cancel()
            self.gif_worker.wait(3000)
        super().closeEvent(event)
