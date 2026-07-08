import sys
import os
import importlib.util
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor

# Windows 控制台 UTF-8 编码
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# 将脚本目录加入 path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import QRect
from PyQt5.QtGui import QIcon

from config import DEBUG_OCR, MAX_DEBUG_IMAGES, QUESTION_BANK_PATH
from question_bank import QuestionBank, expand_answer_parts
from capture import capture_region, compute_hash, has_hash_changed
from overlay import CaptureRegion, ResultWindow
from settings_dialog import SettingsDialog, load_settings

DEBUG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "debug")
ERROR_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "error.log")


def log_exception(exc_type, exc_value, exc_tb):
    text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    try:
        with open(ERROR_LOG, "a", encoding="utf-8") as f:
            f.write("\n" + "=" * 80 + "\n")
            f.write(text)
    except Exception:
        pass
    return text


def handle_uncaught_exception(exc_type, exc_value, exc_tb):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return

    text = log_exception(exc_type, exc_value, exc_tb)
    print(text)
    app = QApplication.instance()
    if app is not None:
        QMessageBox.critical(None, "程序错误", f"程序遇到错误，详情已写入:\n{ERROR_LOG}\n\n{exc_value}")


sys.excepthook = handle_uncaught_exception


def check_dependencies():
    """快速检查外部依赖是否可用，不在启动时加载 EasyOCR/PyTorch。"""
    missing = []
    for module, package in [
        ("easyocr", "easyocr"),
        ("PyQt5", "PyQt5"),
        ("PIL", "Pillow"),
        ("xlrd", "xlrd"),
        ("openpyxl", "openpyxl"),
    ]:
        if importlib.util.find_spec(module) is None:
            missing.append(package)
    if missing:
        print(f"[错误] 缺少依赖: {', '.join(missing)}")
        print("请运行: pip install -r requirements.txt")
        return False
    return True


def main():
    if not check_dependencies():
        input("按回车退出...")
        sys.exit(1)

    app = QApplication(sys.argv)

    # 设置程序图标
    if getattr(sys, 'frozen', False):
        icon_path = os.path.join(sys._MEIPASS, "app_icon.ico")
    else:
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_icon.ico")
    if os.path.isfile(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    # ========== 加载上次保存的设置 ==========
    saved = load_settings()

    # ========== 弹出设置对话框选择题库 ==========
    # 优先使用保存的路径，其次使用默认路径
    saved_path = saved.get("path", "")
    if not saved_path or not os.path.isfile(saved_path):
        saved_path = QUESTION_BANK_PATH  # 可能为空，让用户选择

    settings_dlg = SettingsDialog(
        current_path=saved_path,
        question_col=saved.get("question_col", 1),
        answer_col=saved.get("answer_col", 2),
        option_cols=saved.get("option_cols", {}),
        font_size=saved.get("font_size", 25),
    )
    if settings_dlg.exec_() != SettingsDialog.Accepted:
        print("[退出] 用户取消了题库选择")
        sys.exit(0)

    settings = settings_dlg.get_settings()
    bank_path = settings["path"]
    question_col = settings["question_col"]
    answer_col = settings["answer_col"]
    option_cols = settings.get("option_cols", {})
    font_size = settings["font_size"]

    # ========== 加载题库 ==========
    print(f"[启动] 加载题库: {bank_path}")
    print(f"[启动] 题目列: 第{question_col + 1}列, 答案列: 第{answer_col + 1}列")
    try:
        qb = QuestionBank(
            path=bank_path,
            question_col=question_col,
            answer_col=answer_col,
            option_cols=option_cols,
        )
    except Exception as e:
        print(f"[错误] 加载题库失败: {e}")
        input("按回车退出...")
        sys.exit(1)

    screen = app.primaryScreen()

    # ========== 创建窗口 ==========
    capture_box = CaptureRegion()
    result_win = ResultWindow()
    result_win.set_font_size(font_size)

    # 在识别框右键菜单中添加"设置"选项
    capture_box.open_settings.connect(lambda: _open_settings(capture_box, result_win, qb_ref))

    capture_box.show()
    result_win.show()

    prev_hash = [None]
    poll_count = [0]
    last_text = [""]
    pending_future = [None]
    executor = ThreadPoolExecutor(max_workers=1)
    threading.Thread(target=_warmup_ocr, daemon=True).start()

    # 用列表包裹 qb 以便在设置变更时替换
    qb_ref = [qb]

    def _open_settings(capture_box, result_win, qb_ref):
        """打开设置对话框，重新加载题库和更新字体"""
        was_locked = capture_box.is_locked()
        capture_box.poll_timer.stop()
        future = pending_future[0]
        if future is not None:
            future.cancel()
            pending_future[0] = None
        if was_locked:
            capture_box.unlock()

        try:
            dlg = SettingsDialog(
                current_path=qb_ref[0].path,
                question_col=qb_ref[0].question_col,
                answer_col=qb_ref[0].answer_col,
                option_cols=qb_ref[0].option_cols,
                font_size=result_win._font_size,
            )
            if dlg.exec_() == SettingsDialog.Accepted:
                s = dlg.get_settings()

                # 更新字体大小
                result_win.set_font_size(s["font_size"])

                # 更新题库（如果路径或列变了）
                if (s["path"] != qb_ref[0].path or
                        s["question_col"] != qb_ref[0].question_col or
                        s["answer_col"] != qb_ref[0].answer_col or
                        s.get("option_cols", {}) != qb_ref[0].option_cols):
                    try:
                        new_qb = QuestionBank(
                            path=s["path"],
                            question_col=s["question_col"],
                            answer_col=s["answer_col"],
                            option_cols=s.get("option_cols", {}),
                        )
                    except Exception as e:
                        print(f"[错误] 加载题库失败: {e}")
                        QMessageBox.warning(result_win, "题库加载失败", str(e))
                    else:
                        qb_ref[0] = new_qb
                        last_text[0] = ""
                        prev_hash[0] = None
                        result_win.update_question("等待识别...")
                        result_win.update_answers([])
                        result_win.set_status("题库已切换，等待识别...")
                        print(f"[设置] 题库已切换: {s['path']}")
        except Exception as e:
            log_exception(type(e), e, e.__traceback__)
            QMessageBox.warning(result_win, "设置失败", f"{e}\n\n详情已写入: {ERROR_LOG}")
        finally:
            if was_locked:
                capture_box.lock()
            capture_box.poll_timer.start()

    def on_poll():
        future = pending_future[0]
        if future is not None:
            if future.done():
                pending_future[0] = None
                try:
                    text, results = future.result()
                except Exception as e:
                    result_win.set_status(f"OCR 错误: {e}")
                    print(f"[OCR错误] {e}")
                    return
                _handle_ocr_result(text, results)
            else:
                return

        if not capture_box.is_locked():
            return

        poll_count[0] += 1
        rect = capture_box.get_capture_rect()
        if rect.width() < 10 or rect.height() < 10:
            return

        try:
            img = capture_region(screen, rect.x(), rect.y(), rect.width(), rect.height())
        except Exception as e:
            print(f"[截图错误] {e}")
            return

        if poll_count[0] % 10 == 0:
            print(f"[轮询#{poll_count[0]}] 区域=({rect.x()},{rect.y()},{rect.width()},{rect.height()})")

        curr_hash = compute_hash(img)
        if not has_hash_changed(prev_hash[0], curr_hash):
            return

        prev_hash[0] = curr_hash
        result_win.set_status("识别中...")
        pending_future[0] = executor.submit(_recognize_and_match, img, qb_ref[0], poll_count[0])

    def _handle_ocr_result(text, results):
        if not text or len(text) < 3:
            if last_text[0]:
                result_win.set_status("未检测到文字")
                last_text[0] = ""
            print(f"[OCR] 文本太短: \"{text}\"")
            return

        if text == last_text[0]:
            return

        last_text[0] = text
        print(f"[OCR识别] ({len(text)}字): {text[:80]}...")
        result_win.update_question(text)
        print(f"[匹配] 找到 {len(results)} 条结果")
        result_win.update_answers(results)

    capture_box.poll_timer.timeout.connect(on_poll)
    capture_box.poll_timer.start()

    print("[启动] 答题参考助手已运行")
    print("  - 识别框: 拖拽/缩放选框覆盖题目区域，右键锁定开始识别")
    print("  - 结果窗口: 自由拖动到任何位置")
    print("  - 右键菜单: 锁定/解锁/设置/退出")
    try:
        sys.exit(app.exec_())
    finally:
        executor.shutdown(wait=False)


def _recognize_and_match(img, question_bank, poll_count):
    from ocr_engine import recognize, save_debug_image

    text = recognize(img)
    if (not text or len(text) < 3) and DEBUG_OCR:
        os.makedirs(DEBUG_DIR, exist_ok=True)
        debug_path = os.path.join(DEBUG_DIR, f"debug_{poll_count}.png")
        save_debug_image(img, debug_path)
        _trim_debug_images(DEBUG_DIR)
    return text, _expand_results(question_bank.match(text), text) if text else []


def _warmup_ocr():
    try:
        from ocr_engine import warmup
        warmup()
        print("[OCR] 预热完成")
    except Exception as e:
        print(f"[OCR] 预热失败: {e}")


def _expand_results(results, ocr_text):
    """把题库答案 A/B/C/D 补全为 A + OCR/题库中的选项内容。"""
    expanded = []
    for result in results:
        if len(result) >= 4:
            score, question, answer, options = result[:4]
        else:
            score, question, answer = result
            options = {}
        answer_code, details, copy_text = expand_answer_parts(answer, options, question, ocr_text)
        expanded.append((score, question, answer, answer_code, details, copy_text))
    return expanded


def _trim_debug_images(debug_dir):
    """限制调试截图数量，避免 debug 目录无限增长。"""
    try:
        images = [
            os.path.join(debug_dir, name)
            for name in os.listdir(debug_dir)
            if name.lower().endswith((".png", ".jpg", ".jpeg"))
        ]
        images.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        for path in images[MAX_DEBUG_IMAGES:]:
            os.remove(path)
    except Exception as e:
        print(f"[调试] 清理失败: {e}")


if __name__ == "__main__":
    main()
