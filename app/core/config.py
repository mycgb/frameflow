"""抽帧任务的配置模型。

UI 只负责收集参数并生成 ExtractConfig；核心引擎不依赖任何 GUI 代码，
方便后续接入命令行、Web 接口或其他前端。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class ExtractConfig:
    output_dir: str = ""

    # 输出图片
    image_format: str = "jpg"          # jpg / png / webp
    quality: int = 95                  # 1-100
    resize_mode: str = "original"      # original / width / height / scale
    resize_value: int = 100            # width/height 为像素；scale 为百分比

    # 抽帧规则
    frame_mode: str = "all"            # all / every_n / per_second
    frame_value: int = 1               # every_n 的间隔；per_second 的每秒帧数
    start_time: float = 0.0            # 秒；0 表示从头开始
    end_time: float = 0.0              # 秒；0 表示到结尾

    # 文件组织
    subfolder_per_video: bool = True   # 每个视频建一个同名子文件夹
    name_pattern: str = "{name}_{index:06d}"
    overwrite: bool = False
    max_frames: int = 0                # 0 表示不限制

    # 扩展位：后续可放水印、裁剪、去黑边等处理器配置
    extra: Dict[str, object] = field(default_factory=dict)

    def normalized(self) -> "ExtractConfig":
        """返回一份修正过非法取值的副本，避免 UI 传进来的脏数据影响引擎。"""
        cfg = self
        cfg.image_format = str(cfg.image_format).lower()
        if cfg.image_format not in ("jpg", "jpeg", "png", "webp"):
            cfg.image_format = "jpg"
        cfg.quality = max(1, min(100, int(cfg.quality)))
        if cfg.resize_mode not in ("original", "width", "height", "scale"):
            cfg.resize_mode = "original"
        cfg.resize_value = max(1, int(cfg.resize_value))
        if cfg.frame_mode not in ("all", "every_n", "per_second"):
            cfg.frame_mode = "all"
        cfg.frame_value = max(1, int(cfg.frame_value))
        cfg.start_time = max(0.0, float(cfg.start_time))
        cfg.end_time = max(0.0, float(cfg.end_time))
        if cfg.end_time and cfg.end_time <= cfg.start_time:
            cfg.end_time = 0.0
        cfg.max_frames = max(0, int(cfg.max_frames))
        if not cfg.name_pattern or "{index" not in cfg.name_pattern:
            cfg.name_pattern = "{name}_{index:06d}"
        return cfg
