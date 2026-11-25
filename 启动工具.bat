@echo off
chcp 65001 >nul
cd /d "%~dp0"

python -c "import PySide6, cv2, PIL" 2>nul
if errorlevel 1 (
    echo [提示] 当前 Python 缺少依赖，正在自动安装 PySide6 / OpenCV / Pillow ...
    python -m pip install PySide6 opencv-python-headless Pillow
)

python main.py
pause
