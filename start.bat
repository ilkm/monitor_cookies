@echo off
chcp 65001 >nul
REM 自动安装依赖并启动 main.py

REM 切换到脚本所在目录
cd /d %~dp0

REM 检查 Python 是否已安装
python --version >nul 2>nul
if errorlevel 1 (
    echo [错误] 未检测到 Python，请先安装 Python。
    pause
    exit /b 1
)

REM 检查依赖是否已安装（以 fastapi 为例）
python -c "import fastapi" >nul 2>nul
if errorlevel 1 (
    echo [提示] 检测到依赖未安装，正在自动安装 requirements.txt ...
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [错误] 依赖安装失败，请检查 requirements.txt。
        pause
        exit /b 1
    )
) else (
    echo [提示] 依赖已安装，跳过安装步骤。
)

REM 启动 main.py
python main.py

REM 保持窗口，便于查看输出
pause 