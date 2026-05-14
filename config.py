import os
import sys


def _get_base_dir():
    """获取程序基础目录"""
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包后的路径
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _find_tesseract():
    """查找 tesseract，优先使用打包目录内的版本"""
    base_dir = _get_base_dir()

    # 1. 环境变量指定
    env_cmd = os.environ.get("TESSERACT_CMD")
    if env_cmd and os.path.isfile(env_cmd):
        return env_cmd

    # 2. 打包目录内的 Tesseract-OCR（Windows 懒人包）
    local_tesseract = os.path.join(base_dir, "Tesseract-OCR", "tesseract.exe")
    if os.path.isfile(local_tesseract):
        return local_tesseract

    # 3. 上级目录（懒人包目录结构）
    parent_tesseract = os.path.join(os.path.dirname(base_dir), "Tesseract-OCR", "tesseract.exe")
    if os.path.isfile(parent_tesseract):
        return parent_tesseract

    if sys.platform == "win32":
        # 4. Windows 系统默认安装路径
        default_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        if os.path.isfile(default_path):
            return default_path
        return default_path
    else:
        # Linux/macOS: 通常在 PATH 中
        import shutil
        which = shutil.which("tesseract")
        if which:
            return which
        return "tesseract"


# 题库路径（默认为空，首次运行时让用户选择）
QUESTION_BANK_PATH = ""

# Tesseract 配置
TESSERACT_CMD = _find_tesseract()
TESSERACT_LANG = "chi_sim+eng"

# 轮询间隔（秒）
POLL_INTERVAL = 0.5

# 变化检测阈值（哈希差异比特数，超过此值认为内容变化）
CHANGE_THRESHOLD = 2

# 匹配阈值（0-1，SequenceMatcher 相似度，低于此值不显示）
MATCH_THRESHOLD = 0.35

# 显示结果数量
MAX_RESULTS = 3

# 窗口配置
WINDOW_OPACITY = 0.6
WINDOW_MIN_WIDTH = 800
WINDOW_MIN_HEIGHT = 20

# 字体大小（可在设置中动态调整）
FONT_SIZE = 25
