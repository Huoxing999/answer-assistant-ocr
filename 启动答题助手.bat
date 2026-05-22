@echo off
chcp 65001 >nul 2>&1
title 答题参考助手
cd /d "%~dp0"
python launch.py
if errorlevel 1 (
    echo.
    echo 启动失败，请确保已安装 Python 3.8+
    echo 下载地址: https://www.python.org/downloads/
    pause
)
