"""
答题参考助手 - 一键启动器
双击运行，自动检测并安装依赖，首次运行会下载 OCR 模型（约 100MB）
"""
import subprocess
import sys
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REQUIREMENTS = {
    "PyQt5": "PyQt5>=5.15",
    "easyocr": "easyocr>=1.7",
    "PIL": "Pillow>=9.0",
    "xlrd": "xlrd>=2.0",
    "openpyxl": "openpyxl>=3.0",
    "pyperclip": "pyperclip>=1.8",
}


def check_and_install():
    """检查依赖，缺失的自动安装（通过 pip list 检查，避免 DLL 冲突）"""
    result = subprocess.run(
        [sys.executable, "-m", "pip", "list", "--format=freeze"],
        capture_output=True, text=True,
    )
    installed = {line.split("==")[0].lower() for line in result.stdout.splitlines()}

    # 包名到 pip 包名的映射
    pip_names = {
        "PyQt5": "PyQt5", "easyocr": "easyocr", "PIL": "Pillow",
        "xlrd": "xlrd", "openpyxl": "openpyxl", "pyperclip": "pyperclip",
    }

    missing = []
    for module, package in REQUIREMENTS.items():
        pip_name = pip_names.get(module, package.split(">=")[0].split("==")[0])
        if pip_name.lower() not in installed:
            missing.append(package)

    if not missing:
        return True

    print(f"[启动器] 缺少 {len(missing)} 个依赖，正在自动安装...")
    for pkg in missing:
        print(f"  安装 {pkg} ...")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", pkg],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            print(f"  安装失败: {pkg}")
            print(f"  {result.stderr}")
            return False
        print(f"  安装成功: {pkg}")

    print("[启动器] 所有依赖安装完成\n")
    return True


def pre_download_models():
    """预下载 EasyOCR 模型（首次运行时），在子进程中执行避免 DLL 冲突"""
    model_dir = os.path.join(os.path.expanduser("~"), ".EasyOCR")
    if os.path.isdir(model_dir) and os.listdir(model_dir):
        return True

    print("[启动器] 首次运行，正在下载 OCR 模型（约 100MB）...")
    print("[启动器] 请耐心等待...\n")
    result = subprocess.run(
        [sys.executable, "-c",
         "import easyocr; easyocr.Reader(['ch_sim','en'], gpu=False, verbose=False)"],
        capture_output=False,
    )
    if result.returncode == 0:
        print("[启动器] 模型下载完成\n")
        return True

    print("[启动器] 模型下载失败，请检查网络连接后重试")
    return False


def main():
    os.chdir(SCRIPT_DIR)

    print("=" * 50)
    print("  答题参考助手 - 启动器")
    print("=" * 50)
    print()

    # 1. 检查并安装依赖
    if not check_and_install():
        input("\n依赖安装失败，按回车退出...")
        sys.exit(1)

    # 2. 预下载模型
    if not pre_download_models():
        input("\n按回车退出...")
        sys.exit(1)

    # 3. 启动主程序
    print("[启动器] 正在启动答题参考助手...\n")
    main_py = os.path.join(SCRIPT_DIR, "main.py")
    if not os.path.isfile(main_py):
        print(f"[错误] 找不到 main.py: {main_py}")
        input("按回车退出...")
        sys.exit(1)

    os.execv(sys.executable, [sys.executable, main_py])


if __name__ == "__main__":
    main()
