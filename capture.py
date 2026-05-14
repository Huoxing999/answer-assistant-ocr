import io
from PIL import Image
from PyQt5.QtCore import QBuffer, QIODevice
from config import CHANGE_THRESHOLD


def capture_region(screen, x, y, w, h):
    """用 QScreen.grabWindow 截取指定区域，返回 PIL Image"""
    pixmap = screen.grabWindow(0, x, y, w, h)

    # QPixmap -> PNG bytes -> PIL Image
    buffer = QBuffer()
    buffer.open(QIODevice.WriteOnly)
    pixmap.save(buffer, "PNG")
    buffer.close()

    img = Image.open(io.BytesIO(buffer.data()))
    return img.convert("RGB")


def compute_hash(image, hash_size=16):
    """计算感知哈希 (pHash)，返回整数"""
    gray = image.convert("L").resize((hash_size, hash_size), Image.LANCZOS)
    pixels = list(gray.getdata())
    avg = sum(pixels) / len(pixels)
    bits = 0
    for p in pixels:
        bits = (bits << 1) | (1 if p > avg else 0)
    return bits


def hamming_distance(h1, h2):
    """计算两个哈希的汉明距离（不同比特数）"""
    x = h1 ^ h2
    count = 0
    while x:
        count += 1
        x &= x - 1
    return count


def has_changed(prev_hash, current_image):
    """检测屏幕区域内容是否变化"""
    if prev_hash is None:
        return True
    curr_hash = compute_hash(current_image)
    dist = hamming_distance(prev_hash, curr_hash)
    return dist > CHANGE_THRESHOLD
