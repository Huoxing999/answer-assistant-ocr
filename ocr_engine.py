import pytesseract
from PIL import Image, ImageFilter, ImageOps
from config import TESSERACT_CMD, TESSERACT_LANG

# 设置 Tesseract 路径
pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

# Tesseract 配置: OEM 1=LSTM引擎, PSM 6=统一文本块
TESSERACT_CONFIG = "--oem 1 --psm 6"

# 缩放倍数（屏幕截图96DPI，放大后接近300DPI）
SCALE_FACTOR = 2


def _otsu_threshold(gray_image):
    """用直方图计算 Otsu 最佳阈值（纯 PIL 实现）"""
    hist = gray_image.histogram()
    total = sum(hist)
    sum_all = sum(i * h for i, h in enumerate(hist))

    sum_bg = 0
    w_bg = 0
    max_var = 0
    threshold = 0

    for t in range(256):
        w_bg += hist[t]
        if w_bg == 0:
            continue
        w_fg = total - w_bg
        if w_fg == 0:
            break

        sum_bg += t * hist[t]
        mean_bg = sum_bg / w_bg
        mean_fg = (sum_all - sum_bg) / w_fg

        var = w_bg * w_fg * (mean_bg - mean_fg) ** 2
        if var > max_var:
            max_var = var
            threshold = t

    return threshold


def preprocess(image):
    """图像预处理：放大 → 灰度 → 去噪 → 锐化 → Otsu 二值化"""
    # 1. 放大图像（提高小字识别率）
    w, h = image.size
    scaled = image.resize((w * SCALE_FACTOR, h * SCALE_FACTOR), Image.LANCZOS)

    # 2. 灰度化
    gray = scaled.convert("L")

    # 3. 自动对比度增强
    gray = ImageOps.autocontrast(gray, cutoff=1)

    # 4. 中值滤波去噪（保留边缘）
    gray = gray.filter(ImageFilter.MedianFilter(size=3))

    # 5. 锐化（让文字边缘更清晰）
    gray = gray.filter(ImageFilter.SHARPEN)

    # 6. Otsu 自适应二值化
    threshold = _otsu_threshold(gray)
    binary = gray.point(lambda x: 0 if x < threshold else 255)

    return binary


def recognize(image):
    """对 PIL Image 进行 OCR 识别，返回文本"""
    processed = preprocess(image)
    text = pytesseract.image_to_string(
        processed, lang=TESSERACT_LANG, config=TESSERACT_CONFIG
    )
    return text.strip()


def recognize_with_debug(image, debug_path=None):
    """OCR 识别，可选保存中间图像用于调试"""
    processed = preprocess(image)
    if debug_path:
        processed.save(debug_path)
        print(f"[调试] 预处理图像已保存: {debug_path}")
    text = pytesseract.image_to_string(
        processed, lang=TESSERACT_LANG, config=TESSERACT_CONFIG
    )
    return text.strip()
