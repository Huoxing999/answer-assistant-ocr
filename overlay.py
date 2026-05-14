import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QMenu,
    QScrollArea
)
from PyQt5.QtCore import Qt, QTimer, QRect, QPoint, pyqtSignal
from PyQt5.QtGui import QPainter, QPen, QColor, QCursor, QBrush

from config import (
    WINDOW_OPACITY, WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT,
    POLL_INTERVAL, FONT_SIZE
)


class AnswerLabel(QLabel):
    """可点击复制的答案标签"""
    clicked = pyqtSignal(str)

    def __init__(self, text, font_size=FONT_SIZE, parent=None):
        super().__init__(parent)
        self.full_text = text
        self.setText(text)
        self.setWordWrap(True)
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self._font_size = font_size
        self._apply_style()

    def _apply_style(self):
        self.setStyleSheet(f"""
            QLabel {{
                color: #ffffff;
                background: rgba(0, 120, 215, 220);
                border: 3px solid #0078D7;
                border-radius: 8px;
                padding: 16px 20px;
                margin: 8px 0;
                font-size: {self._font_size}px;
                font-weight: bold;
            }}
            QLabel:hover {{
                background: rgba(0, 150, 255, 240);
                border-color: #FFD700;
            }}
        """)

    def set_font_size(self, size):
        self._font_size = size
        self._apply_style()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            QApplication.clipboard().setText(self.full_text)
            self.clicked.emit(self.full_text)


# ============================================================
#  识别框 - 独立的透明选框，用于框选屏幕区域
# ============================================================
class CaptureRegion(QWidget):
    """可拖拽/缩放的透明选框，用于框选 OCR 识别区域"""
    open_settings = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._drag_pos = None
        self._resize_edge = None
        self._edge_margin = 12
        self._locked = False
        self._locked_rect = None

        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMinimumSize(100, 30)
        self.resize(600, 100)
        self.move(300, 300)
        self.setCursor(Qt.SizeAllCursor)

        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(int(POLL_INTERVAL * 1000))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 半透明背景
        painter.setBrush(QBrush(QColor(0, 0, 0, 30)))
        painter.setPen(Qt.NoPen)
        painter.drawRect(self.rect())

        # 边框：锁定=蓝色，未锁定=绿色
        border_color = QColor(0, 120, 255, 255) if self._locked else QColor(0, 255, 100, 255)
        pen = QPen(border_color, 3, Qt.SolidLine)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(self.rect().adjusted(1, 1, -1, -1))

        # 四角标记
        corner_len = 20
        pen2 = QPen(QColor(255, 255, 0, 255), 4, Qt.SolidLine)
        painter.setPen(pen2)
        r = self.rect()
        painter.drawLine(r.topLeft(), r.topLeft() + QPoint(corner_len, 0))
        painter.drawLine(r.topLeft(), r.topLeft() + QPoint(0, corner_len))
        painter.drawLine(r.topRight(), r.topRight() + QPoint(-corner_len, 0))
        painter.drawLine(r.topRight(), r.topRight() + QPoint(0, corner_len))
        painter.drawLine(r.bottomLeft(), r.bottomLeft() + QPoint(corner_len, 0))
        painter.drawLine(r.bottomLeft(), r.bottomLeft() + QPoint(0, -corner_len))
        painter.drawLine(r.bottomRight(), r.bottomRight() + QPoint(-corner_len, 0))
        painter.drawLine(r.bottomRight(), r.bottomRight() + QPoint(0, -corner_len))

        # 中间提示文字
        if not self._locked:
            painter.setPen(QColor(255, 255, 255, 180))
            painter.drawText(self.rect(), Qt.AlignCenter, "拖拽移动 | 缩放大小 | 右键菜单")
        else:
            painter.setPen(QColor(0, 180, 255, 200))
            painter.drawText(self.rect(), Qt.AlignCenter, "已锁定 | 右键菜单")

        painter.end()

    def lock(self):
        self._locked = True
        self._locked_rect = QRect(
            self.geometry().x(), self.geometry().y(),
            self.geometry().width(), self.geometry().height()
        )
        self.setCursor(Qt.ArrowCursor)
        self.update()

    def unlock(self):
        self._locked = False
        self._locked_rect = None
        self.setCursor(Qt.SizeAllCursor)
        self.update()

    def is_locked(self):
        return self._locked

    def get_capture_rect(self):
        if self._locked and self._locked_rect:
            return self._locked_rect
        geo = self.geometry()
        return QRect(geo.x(), geo.y(), geo.width(), geo.height())

    def _get_resize_edge(self, pos):
        rect = self.rect()
        m = self._edge_margin
        edges = []
        if pos.x() < m:
            edges.append("left")
        elif pos.x() > rect.width() - m:
            edges.append("right")
        if pos.y() < m:
            edges.append("top")
        elif pos.y() > rect.height() - m:
            edges.append("bottom")
        return "_".join(edges) if edges else None

    def mousePressEvent(self, event):
        if self._locked:
            event.accept()
            return
        if event.button() == Qt.LeftButton:
            edge = self._get_resize_edge(event.pos())
            if edge:
                self._resize_edge = edge
                self._drag_pos = event.globalPos()
            else:
                self._resize_edge = None
                self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._locked:
            event.accept()
            return
        if event.buttons() & Qt.LeftButton:
            if self._resize_edge:
                diff = event.globalPos() - self._drag_pos
                geo = self.geometry()
                if "right" in self._resize_edge:
                    geo.setWidth(max(100, geo.width() + diff.x()))
                if "bottom" in self._resize_edge:
                    geo.setHeight(max(30, geo.height() + diff.y()))
                if "left" in self._resize_edge:
                    new_w = max(100, geo.width() - diff.x())
                    geo.setLeft(geo.right() - new_w)
                if "top" in self._resize_edge:
                    new_h = max(30, geo.height() - diff.y())
                    geo.setTop(geo.bottom() - new_h)
                self.setGeometry(geo)
                self._drag_pos = event.globalPos()
            else:
                self.move(event.globalPos() - self._drag_pos)
            event.accept()
        else:
            if self._locked:
                return
            edge = self._get_resize_edge(event.pos())
            if edge:
                cursor_map = {
                    "left": Qt.SizeHorCursor, "right": Qt.SizeHorCursor,
                    "top": Qt.SizeVerCursor, "bottom": Qt.SizeVerCursor,
                    "top_left": Qt.SizeFDiagCursor, "top_right": Qt.SizeBDiagCursor,
                    "bottom_left": Qt.SizeBDiagCursor, "bottom_right": Qt.SizeFDiagCursor,
                }
                self.setCursor(cursor_map.get(edge, Qt.ArrowCursor))
            else:
                self.setCursor(Qt.SizeAllCursor)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        self._resize_edge = None

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        if self._locked:
            menu.addAction("解锁选框").triggered.connect(self.unlock)
        else:
            menu.addAction("锁定选框（开始识别）").triggered.connect(self.lock)
        menu.addSeparator()
        menu.addAction("题库设置").triggered.connect(self.open_settings.emit)
        menu.addSeparator()
        menu.addAction("退出").triggered.connect(QApplication.quit)
        menu.exec_(event.globalPos())


# ============================================================
#  结果窗口 - 独立的题目+答案显示窗口
# ============================================================
class ResultWindow(QWidget):
    """独立的结果显示窗口，可自由拖动"""

    def __init__(self):
        super().__init__()
        self._drag_pos = None
        self._font_size = FONT_SIZE
        self._init_ui()

    def _init_ui(self):
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowOpacity(WINDOW_OPACITY)
        self.resize(900, 400)
        self.move(100, 100)

        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # ========== 左侧：题目面板 ==========
        self.question_panel = QWidget()
        self.question_panel.setStyleSheet("""
            background: rgba(15, 15, 15, 245);
            border-radius: 12px;
            border: 3px solid #444;
        """)
        self.question_layout = QVBoxLayout(self.question_panel)
        self.question_layout.setContentsMargins(20, 16, 20, 16)
        self.question_layout.setSpacing(10)

        self.q_title = QLabel("识别题目")
        self.question_layout.addWidget(self.q_title)

        self.question_label = QLabel("等待识别...")
        self.question_label.setWordWrap(True)
        self.question_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.question_layout.addWidget(self.question_label, 1)

        # ========== 右侧：答案面板 ==========
        self.answer_panel = QWidget()
        self.answer_panel.setStyleSheet("""
            background: rgba(15, 15, 15, 245);
            border-radius: 12px;
            border: 3px solid #444;
        """)
        self.answer_layout = QVBoxLayout(self.answer_panel)
        self.answer_layout.setContentsMargins(20, 16, 20, 16)
        self.answer_layout.setSpacing(10)

        self.a_title = QLabel("参考答案")
        self.answer_layout.addWidget(self.a_title)

        # 答案滚动区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical {
                background: rgba(50, 50, 50, 180);
                width: 10px; border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: rgba(150, 150, 150, 200);
                border-radius: 5px; min-height: 30px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        self.answer_container = QWidget()
        self.answer_container.setStyleSheet("background: transparent;")
        self.answer_area = QVBoxLayout(self.answer_container)
        self.answer_area.setSpacing(8)
        self.answer_area.setContentsMargins(4, 4, 4, 4)
        self.answer_area.addStretch()

        self.scroll_area.setWidget(self.answer_container)
        self.answer_layout.addWidget(self.scroll_area, 1)

        self.status_label = QLabel("等待识别...")
        self.answer_layout.addWidget(self.status_label)

        self.main_layout.addWidget(self.question_panel, 1)
        self.main_layout.addWidget(self.answer_panel, 1)

        # 应用初始字体
        self._apply_font_sizes()

    def _apply_font_sizes(self):
        """根据当前 _font_size 动态更新所有字体"""
        s = self._font_size
        self.q_title.setStyleSheet(f"""
            color: #FFD700; font-size: {s + 10}px; font-weight: bold;
            border: none; background: transparent; padding: 4px;
        """)
        self.question_label.setStyleSheet(f"""
            color: #ddd; font-size: {s}px;
            border: none; background: transparent; padding: 8px;
        """)
        self.a_title.setStyleSheet(f"""
            color: #FFD700; font-size: {s + 10}px; font-weight: bold;
            border: none; background: transparent; padding: 4px;
        """)
        self.status_label.setStyleSheet(f"""
            color: #bbb; font-size: {s - 6}px;
            border: none; background: transparent; padding-top: 6px;
        """)

    def set_font_size(self, size):
        """动态调整字体大小"""
        self._font_size = size
        self._apply_font_sizes()
        # 刷新答案区的字体
        self._refresh_answer_fonts()

    def _refresh_answer_fonts(self):
        """刷新答案区域中所有 AnswerLabel 的字体"""
        for i in range(self.answer_area.count()):
            item = self.answer_area.itemAt(i)
            if item and item.widget():
                w = item.widget()
                if isinstance(w, AnswerLabel):
                    w.set_font_size(self._font_size)
                elif isinstance(w, QLabel):
                    # 匹配度标题
                    txt = w.text()
                    if "匹配度" in txt:
                        w.setStyleSheet(f"""
                            color: #4FC3F7; font-size: {self._font_size - 4}px; font-weight: bold;
                            border: none; background: transparent; margin-top: 8px;
                        """)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QBrush(QColor(0, 0, 0, 10)))
        painter.setPen(Qt.NoPen)
        painter.drawRect(self.rect())

        pen = QPen(QColor(100, 100, 100, 200), 2, Qt.SolidLine)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(self.rect().adjusted(1, 1, -1, -1))
        painter.end()

    def update_question(self, text):
        self.question_label.setText(text)

    def update_answers(self, results):
        while self.answer_area.count():
            child = self.answer_area.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        s = self._font_size

        if not results:
            label = QLabel("未找到匹配题目")
            label.setStyleSheet(f"""
                color: #ff6b6b; font-size: {s}px; font-weight: bold;
                border: none; background: transparent;
            """)
            self.answer_area.addWidget(label)
            self.status_label.setText("未匹配")
            self.answer_area.addStretch()
            return

        for i, (score, question, answer) in enumerate(results):
            q_short = question[:50] + "..." if len(question) > 50 else question
            header = QLabel(f"匹配度 {score:.0%} | {q_short}")
            header.setStyleSheet(f"""
                color: #4FC3F7; font-size: {s - 4}px; font-weight: bold;
                border: none; background: transparent; margin-top: 8px;
            """)
            self.answer_area.addWidget(header)

            ans_label = AnswerLabel(answer, font_size=s)
            ans_label.clicked.connect(lambda t: self._on_copied(t))
            self.answer_area.addWidget(ans_label)

        self.answer_area.addStretch()

        # 自动复制最佳答案
        best_answer = results[0][2]
        QApplication.clipboard().setText(best_answer)
        self._show_copied_status(len(results))

    def set_status(self, text):
        self.status_label.setText(text)

    def _show_copied_status(self, count):
        s = self._font_size
        self.status_label.setText(f"已自动复制最佳答案 | 匹配 {count} 条")
        self.status_label.setStyleSheet(f"""
            color: #00FF88; font-size: {s - 4}px; font-weight: bold;
            border: none; background: transparent;
        """)
        QTimer.singleShot(2000, lambda: self.status_label.setStyleSheet(f"""
            color: #bbb; font-size: {s - 6}px;
            border: none; background: transparent; padding-top: 6px;
        """))

    def _on_copied(self, text):
        QApplication.clipboard().setText(text)
        s = self._font_size
        self.status_label.setText("已复制到剪贴板!")
        self.status_label.setStyleSheet(f"""
            color: #00FF88; font-size: {s - 4}px; font-weight: bold;
            border: none; background: transparent;
        """)
        QTimer.singleShot(2000, lambda: self.status_label.setStyleSheet(f"""
            color: #bbb; font-size: {s - 6}px;
            border: none; background: transparent; padding-top: 6px;
        """))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and self._drag_pos:
            self.move(event.globalPos() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        font_menu = menu.addMenu("字体大小")
        for size in [20, 28, 36, 48, 60, 72, 84]:
            action = font_menu.addAction(f"{size}px")
            action.triggered.connect(lambda checked, s=size: self.set_font_size(s))
        menu.addSeparator()
        menu.addAction("退出").triggered.connect(QApplication.quit)
        menu.exec_(event.globalPos())
