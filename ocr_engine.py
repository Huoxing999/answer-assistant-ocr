import atexit
import json
import os
import subprocess
import sys
import tempfile
import threading
import uuid


_service = None
_service_lock = threading.Lock()


def _service_script():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "ocr_service.py")


def _start_service():
    global _service
    if _service is not None and _service.poll() is None:
        return _service

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    _service = subprocess.Popen(
        [sys.executable, _service_script()],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        env=env,
        creationflags=creationflags,
    )
    return _service


def _stop_service():
    global _service
    proc = _service
    _service = None
    if proc is None or proc.poll() is not None:
        return
    try:
        proc.stdin.write((json.dumps({"cmd": "quit"}) + "\n").encode("utf-8"))
        proc.stdin.flush()
        proc.wait(timeout=2)
    except Exception:
        proc.kill()


atexit.register(_stop_service)


def warmup():
    """Start the OCR service and load the EasyOCR reader in advance."""
    with _service_lock:
        proc = _start_service()
        request = json.dumps({"cmd": "warmup"}, ensure_ascii=False) + "\n"
        proc.stdin.write(request.encode("utf-8"))
        proc.stdin.flush()
        payload = _read_response(proc)
        if not payload.get("ok"):
            raise RuntimeError(payload.get("error", "OCR warmup failed"))


def recognize(image):
    """对 PIL Image 进行 OCR 识别，返回文本。OCR 在独立进程中运行，避免 PyQt/torch DLL 冲突。"""
    with _service_lock:
        proc = _start_service()
        img_path = os.path.join(tempfile.gettempdir(), f"answer_ocr_{uuid.uuid4().hex}.png")
        try:
            image.convert("RGB").save(img_path)
            request = json.dumps({"image": img_path}, ensure_ascii=False) + "\n"
            proc.stdin.write(request.encode("utf-8"))
            proc.stdin.flush()
            payload = _read_response(proc)
            if not payload.get("ok"):
                raise RuntimeError(payload.get("error", "OCR 服务错误"))
            return payload.get("text", "")
        finally:
            try:
                os.remove(img_path)
            except OSError:
                pass


def _read_response(proc):
    while True:
        line = proc.stdout.readline()
        if not line:
            raise RuntimeError("OCR 服务无响应")
        try:
            text = line.decode("utf-8")
        except UnicodeDecodeError:
            continue
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            continue


def recognize_with_debug(image, debug_path=None):
    """OCR 识别，可选保存原始图像用于调试。"""
    if debug_path:
        save_debug_image(image, debug_path)
    return recognize(image)


def save_debug_image(image, debug_path):
    """仅保存调试截图，不重复执行 OCR。"""
    image.convert("RGB").save(debug_path)
    print(f"[调试] 图像已保存: {debug_path}")
