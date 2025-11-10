@echo off
REM 快速启动脚本

cd /d "%~dp0"

echo ========================================
echo 实时字幕系统
echo ========================================
echo.

REM 检查Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到Python,请先安装Python 3.9+
    pause
    exit /b 1
)

REM 检查依赖
python -c "import pyaudio" >nul 2>&1
if errorlevel 1 (
    echo [警告] PyAudio未安装
    echo.
    echo 正在安装依赖...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo [错误] 依赖安装失败
        echo 请手动运行: pip install -r requirements.txt
        pause
        exit /b 1
    )
)

REM 检查.env文件
if not exist .env (
    echo [警告] 未找到.env文件
    echo.
    echo 请先配置API Keys:
    echo 1. copy .env.example .env
    echo 2. 编辑.env文件填入API Keys
    echo.
    pause
    exit /b 1
)

REM 启动程序
echo [启动] 正在启动程序...
echo.
python app\main.py

pause
