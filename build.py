"""
打包脚本：将答题参考助手打包成单个 exe
包含 EasyOCR + PyTorch，用户无需安装 Python
"""
import subprocess
import sys
import os
import shutil

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(PROJECT_DIR, "dist")


def clean():
    """清理旧的打包文件"""
    for d in ["build", "dist"]:
        path = os.path.join(PROJECT_DIR, d)
        if os.path.exists(path):
            shutil.rmtree(path)
            print(f"已清理: {path}")
    import glob
    for f in glob.glob(os.path.join(PROJECT_DIR, "*.spec")):
        os.remove(f)


def build_exe():
    """使用 PyInstaller 打包"""
    icon_path = os.path.join(PROJECT_DIR, "app_icon.ico")
    icon_arg = f"--icon={icon_path}" if os.path.isfile(icon_path) else ""

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onedir",                           # 目录模式（torch 太大，onedir 启动更快）
        "--windowed",                         # 无控制台窗口
        "--name=答题参考助手",
        *([icon_arg] if icon_arg else []),
        # 隐藏导入
        "--hidden-import=easyocr",
        "--hidden-import=torch",
        "--hidden-import=torchvision",
        "--hidden-import=PIL",
        "--hidden-import=xlrd",
        "--hidden-import=openpyxl",
        "--hidden-import=pyperclip",
        "--hidden-import=PyQt5",
        "--hidden-import=PyQt5.QtWidgets",
        "--hidden-import=PyQt5.QtCore",
        "--hidden-import=PyQt5.QtGui",
        "--hidden-import=numpy",
        "--hidden-import=cv2",
        "--hidden-import=scipy",
        "--hidden-import=skimage",
        "--hidden-import=skimage.feature",
        # 收集
        "--collect-all=easyocr",
        "--collect-all=openpyxl",
        # 添加图标
        *([f"--add-data={icon_path};."] if os.path.isfile(icon_path) else []),
        "main.py",
    ]

    print("\n" + "=" * 60)
    print("步骤 1/2：打包 Python 程序...")
    print("=" * 60)
    print("注意: 包含 PyTorch，打包文件较大（约 500MB），请耐心等待\n")

    os.chdir(PROJECT_DIR)
    result = subprocess.run(cmd, capture_output=False)
    return result.returncode == 0


def create_readme():
    """创建使用说明"""
    readme_content = """# 答题参考助手

## 使用方法

1. 双击「答题参考助手.exe」即可运行
2. 首次运行会弹出设置窗口，选择题库文件
3. 选择题目列和答案列
4. 点击确定开始使用

## 注意事项

- 题库支持 .xls、.xlsx、.csv 格式
- 题库第一行必须是表头
- 设置会自动保存，下次启动自动加载
- 首次运行会自动下载 OCR 模型（约 100MB），需要联网

## 快捷操作

- 拖拽/缩放绿色选框覆盖题目
- 右键菜单 → 锁定选框（开始识别）
- 识别到题目后自动复制最佳答案
- 点击题目或答案可直接复制到剪贴板
- 右键菜单 → 题库设置（可随时修改）

## 文件说明

- 答题参考助手.exe - 主程序
- _internal/ - 运行时依赖（勿删）
"""
    out_dir = os.path.join(DIST_DIR, "答题参考助手")
    if not os.path.isdir(out_dir):
        # onedir 模式输出在 dist/答题参考助手/
        out_dir = DIST_DIR
    readme_path = os.path.join(out_dir, "使用说明.txt")
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(readme_content)
    print(f"已创建: {readme_path}")


def main():
    print("=" * 60)
    print("答题参考助手 - 打包工具")
    print("=" * 60)

    clean()

    if not build_exe():
        print("\n打包失败！")
        sys.exit(1)

    create_readme()

    print("\n" + "=" * 60)
    print("打包完成！")
    print(f"输出目录: {DIST_DIR}")
    print("请将 dist/答题参考助手 目录整体打包分发")
    print("=" * 60)


if __name__ == "__main__":
    main()
