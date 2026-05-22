"""
轻量启动器 - 打包成 exe 后双击运行
自动查找系统 Python，安装依赖，启动主程序
"""
import subprocess
import sys
import os
import shutil
import ctypes


def find_python():
    """查找系统 Python"""
    # 1. PATH 中的 python
    python = shutil.which("python")
    if python:
        return python
    # 2. py launcher
    py = shutil.which("py")
    if py:
        return py
    # 3. 常见安装路径
    for p in [
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python312\python.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python311\python.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python310\python.exe"),
        r"C:\Python312\python.exe",
        r"C:\Python311\python.exe",
        r"C:\Python310\python.exe",
    ]:
        if os.path.isfile(p):
            return p
    return None


def show_error(title, msg):
    ctypes.windll.user32.MessageBoxW(0, msg, title, 0x10)


def main():
    # PyInstaller --onefile 会解压到临时目录，必须用 exe 所在的真实目录
    if getattr(sys, 'frozen', False):
        script_dir = os.path.dirname(sys.executable)
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
    launch_py = os.path.join(script_dir, "launch.py")

    if not os.path.isfile(launch_py):
        show_error("答题参考助手", f"找不到启动脚本:\n{launch_py}")
        sys.exit(1)

    python = find_python()
    if not python:
        show_error(
            "答题参考助手",
            "未找到 Python 环境！\n\n"
            "请先安装 Python 3.8+：\nhttps://www.python.org/downloads/\n\n"
            "安装时勾选「Add Python to PATH」"
        )
        sys.exit(1)

    # 用 python 运行 launch.py，替换当前进程
    os.chdir(script_dir)
    os.execv(python, [python, launch_py])


if __name__ == "__main__":
    main()
