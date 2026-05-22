import numpy as np
from PIL import Image

# 必须在 PyQt5 之前导入 torch，否则 DLL 加载冲突
import easyocr

# 初始化 EasyOCR（首次运行会自动下载模型）
_ocr_engine = None


def _get_ocr():
    """懒加载 EasyOCR 引擎（避免 import 时就初始化）"""
    global _ocr_engine
    if _ocr_engine is None:
        _ocr_engine = easyocr.Reader(
            ["ch_sim", "en"],
            gpu=False,
            verbose=False,
        )
    return _ocr_engine


def preprocess(image):
    """保留预处理接口，EasyOCR 自带预处理，此处仅用于调试可视化"""
    return image.convert("RGB")


def recognize(image):
    """对 PIL Image 进行 OCR 识别，返回文本"""
    reader = _get_ocr()
    img_array = np.array(image.convert("RGB"))
    result = reader.readtext(img_array, detail=0)
    return "\n".join(result).strip()


def recognize_with_debug(image, debug_path=None):
    """OCR 识别，可选保存原始图像用于调试"""
    if debug_path:
        image.convert("RGB").save(debug_path)
        print(f"[调试] 图像已保存: {debug_path}")
    return recognize(image)
