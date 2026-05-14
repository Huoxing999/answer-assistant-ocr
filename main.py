import sys
import os

# Windows 控制台 UTF-8 编码
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# 将脚本目录加入 path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QRect
from PyQt5.QtGui import QIcon

from config import TESSERACT_CMD, QUESTION_BANK_PATH
from question_bank import QuestionBank
from ocr_engine import recognize, recognize_with_debug
from capture import capture_region, compute_hash, has_changed
from overlay import CaptureRegion, ResultWindow
from settings_dialog import SettingsDialog, load_settings

# 调试模式：OCR 失败时保存预处理图像
DEBUG_OCR = True
DEBUG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "debug")


def check_dependencies():
    """检查外部依赖是否可用"""
    if not os.path.isfile(TESSERACT_CMD):
        print(f"[错误] Tesseract 未找到: {TESSERACT_CMD}")
        print("请安装 Tesseract OCR: https://github.com/UB-Mannheim/tesseract/wiki")
        print("安装后设置环境变量 TESSERACT_CMD 或修改 config.py")
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
        font_size=saved.get("font_size", 25),
    )
    if settings_dlg.exec_() != SettingsDialog.Accepted:
        print("[退出] 用户取消了题库选择")
        sys.exit(0)

    settings = settings_dlg.get_settings()
    bank_path = settings["path"]
    question_col = settings["question_col"]
    answer_col = settings["answer_col"]
    font_size = settings["font_size"]

    # ========== 加载题库 ==========
    print(f"[启动] 加载题库: {bank_path}")
    print(f"[启动] 题目列: 第{question_col + 1}列, 答案列: 第{answer_col + 1}列")
    try:
        qb = QuestionBank(path=bank_path, question_col=question_col, answer_col=answer_col)
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

    # 用列表包裹 qb 以便在设置变更时替换
    qb_ref = [qb]

    def _open_settings(capture_box, result_win, qb_ref):
        """打开设置对话框，重新加载题库和更新字体"""
        was_locked = capture_box.is_locked()
        if was_locked:
            capture_box.unlock()

        dlg = SettingsDialog(
            current_path=qb_ref[0].path,
            question_col=qb_ref[0].question_col,
            answer_col=qb_ref[0].answer_col,
            font_size=result_win._font_size,
        )
        if dlg.exec_() == SettingsDialog.Accepted:
            s = dlg.get_settings()

            # 更新字体大小
            result_win.set_font_size(s["font_size"])

            # 更新题库（如果路径或列变了）
            if (s["path"] != qb_ref[0].path or
                    s["question_col"] != qb_ref[0].question_col or
                    s["answer_col"] != qb_ref[0].answer_col):
                try:
                    qb_ref[0] = QuestionBank(
                        path=s["path"], question_col=s["question_col"], answer_col=s["answer_col"]
                    )
                    last_text[0] = ""
                    prev_hash[0] = None
                    result_win.update_question("等待识别...")
                    result_win.update_answers([])
                    result_win.set_status("题库已切换，等待识别...")
                    print(f"[设置] 题库已切换: {s['path']}")
                except Exception as e:
                    print(f"[错误] 加载题库失败: {e}")

    def on_poll():
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

        if not has_changed(prev_hash[0], img):
            return

        prev_hash[0] = compute_hash(img)
        result_win.set_status("识别中...")

        try:
            text = recognize(img)
        except Exception as e:
            result_win.set_status(f"OCR 错误: {e}")
            print(f"[OCR错误] {e}")
            return

        if not text or len(text) < 3:
            if last_text[0]:
                result_win.set_status("未检测到文字")
                last_text[0] = ""
            print(f"[OCR] 文本太短: \"{text}\"")
            if DEBUG_OCR:
                try:
                    os.makedirs(DEBUG_DIR, exist_ok=True)
                    debug_path = os.path.join(DEBUG_DIR, f"debug_{poll_count[0]}.png")
                    recognize_with_debug(img, debug_path)
                except Exception as de:
                    print(f"[调试] 保存失败: {de}")
            return

        if text == last_text[0]:
            return

        last_text[0] = text
        print(f"[OCR识别] ({len(text)}字): {text[:80]}...")
        result_win.update_question(text)
        results = qb_ref[0].match(text)
        print(f"[匹配] 找到 {len(results)} 条结果")
        result_win.update_answers(results)

    capture_box.poll_timer.timeout.connect(on_poll)
    capture_box.poll_timer.start()

    print("[启动] 答题参考助手已运行")
    print("  - 识别框: 拖拽/缩放选框覆盖题目区域，右键锁定开始识别")
    print("  - 结果窗口: 自由拖动到任何位置")
    print("  - 右键菜单: 锁定/解锁/设置/退出")
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
