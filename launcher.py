"""
轻量启动器 - 打包成 exe 后双击运行
自动查找系统 Python，安装依赖，启动主程序
"""
import subprocess
import sys
import os
import shutil
import ctypes


def _python_version(python):
    try:
        result = subprocess.run(
            [python, "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"],
            capture_output=True,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            timeout=5,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _is_supported_python(python):
    version = _python_version(python)
    return version in {"3.10", "3.11", "3.12"}


def _uv_python_candidates():
    base = os.path.expandvars(r"%APPDATA%\uv\python")
    if not os.path.isdir(base):
        return []
    candidates = []
    for name in os.listdir(base):
        lower = name.lower()
        if not lower.startswith("cpython-3."):
            continue
        if not any(v in lower for v in ("3.12", "3.11", "3.10")):
            continue
        path = os.path.join(base, name, "python.exe")
        if os.path.isfile(path):
            candidates.append(path)
    return sorted(candidates, reverse=True)


def find_python(script_dir):
    """查找适合 EasyOCR/PyTorch 的 Python，避免使用 Python 3.14。"""
    venv_python = os.path.join(script_dir, ".venv", "Scripts", "python.exe")
    if os.path.isfile(venv_python):
        return venv_python

    for p in [
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python312\python.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python311\python.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python310\python.exe"),
        r"C:\Python312\python.exe",
        r"C:\Python311\python.exe",
        r"C:\Python310\python.exe",
        *_uv_python_candidates(),
    ]:
        if os.path.isfile(p) and _is_supported_python(p):
            return p

    python = shutil.which("python")
    if python and _is_supported_python(python):
        return python

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

    python = find_python(script_dir)
    if not python:
        show_error(
            "答题参考助手",
            "未找到可用的 Python 3.10/3.11/3.12 环境。\n\n"
            "当前 EasyOCR/PyTorch 不建议使用 Python 3.14。\n"
            "请安装 Python 3.11 或使用项目里的 .venv 环境。"
        )
        sys.exit(1)

    # 用 python 运行 launch.py，替换当前进程
    os.chdir(script_dir)
    os.execv(python, [python, launch_py])


if __name__ == "__main__":
    main()
