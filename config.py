import os
import sys


def _get_base_dir():
    """获取程序基础目录"""
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包后的路径
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


# 题库路径（默认为空，首次运行时让用户选择）
QUESTION_BANK_PATH = ""

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
