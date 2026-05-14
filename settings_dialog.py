import os
import sys
import json
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QFileDialog, QLineEdit, QMessageBox, QGroupBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QSpinBox
)
from PyQt5.QtCore import Qt
from question_bank import QuestionBank, read_spreadsheet
from config import FONT_SIZE


def _get_settings_file():
    """获取设置文件路径（支持打包后的路径）"""
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, "settings.json")


def load_settings():
    """从文件加载上次的设置"""
    defaults = {
        "path": "",
        "question_col": 1,
        "answer_col": 2,
        "font_size": FONT_SIZE,
    }
    settings_file = _get_settings_file()
    if os.path.isfile(settings_file):
        try:
            with open(settings_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            defaults.update(data)
        except Exception:
            pass
    return defaults


def save_settings(settings):
    """保存设置到文件"""
    settings_file = _get_settings_file()
    try:
        with open(settings_file, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[设置] 保存失败: {e}")


class SettingsDialog(QDialog):
    """题库设置对话框：选择文件、选择题目列和答案列、字体大小"""

    def __init__(self, current_path=None, question_col=1, answer_col=2,
                 font_size=FONT_SIZE, parent=None):
        super().__init__(parent)
        self.file_path = current_path
        self.question_col = question_col
        self.answer_col = answer_col
        self.font_size = font_size
        self.headers = []
        self.preview_rows = []
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle("设置")
        self.setMinimumWidth(700)
        self.setMinimumHeight(600)

        # 设置对话框自身字体大小
        base = 30
        self.setStyleSheet(f"""
            QDialog {{ background: #1e1e1e; color: #ddd; }}
            QLabel {{ color: #ddd; font-size: {base}px; }}
            QGroupBox {{
                color: #FFD700; font-size: {base}px; font-weight: bold;
                border: 1px solid #555; border-radius: 6px;
                margin-top: 12px; padding-top: 20px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px; padding: 0 6px;
            }}
            QPushButton {{
                background: #0078D7; color: white; border: none;
                border-radius: 6px; padding: 10px 18px; font-size: {base}px;
            }}
            QPushButton:hover {{ background: #005FA3; }}
            QComboBox {{
                background: #2d2d2d; color: #ddd; border: 1px solid #555;
                border-radius: 4px; padding: 8px; font-size: {base}px;
            }}
            QLineEdit {{
                background: #2d2d2d; color: #ddd; border: 1px solid #555;
                border-radius: 4px; padding: 8px; font-size: {base}px;
            }}
            QSpinBox {{
                background: #2d2d2d; color: #ddd; border: 1px solid #555;
                border-radius: 4px; padding: 8px; font-size: {base}px;
            }}
            QTableWidget {{
                background: #2d2d2d; color: #ddd; border: 1px solid #555;
                font-size: {base - 1}px;
            }}
            QHeaderView::section {{
                background: #3a3a3a; color: #FFD700; border: 1px solid #555;
                padding: 6px; font-weight: bold; font-size: {base}px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        # ========== 1. 选择文件 ==========
        file_group = QGroupBox("第一步：选择题库文件")
        file_layout = QVBoxLayout(file_group)

        file_row = QHBoxLayout()
        self.file_input = QLineEdit()
        self.file_input.setPlaceholderText("点击右侧按钮选择题库文件 (.xls / .xlsx / .csv)")
        if self.file_path:
            self.file_input.setText(self.file_path)
        file_row.addWidget(self.file_input, 1)

        browse_btn = QPushButton("浏览...")
        browse_btn.setFixedWidth(140)
        browse_btn.clicked.connect(self._browse_file)
        file_row.addWidget(browse_btn)
        file_layout.addLayout(file_row)

        layout.addWidget(file_group)

        # ========== 2. 选择列 ==========
        col_group = QGroupBox("第二步：选择题目列和答案列（先读取列名）")
        col_layout = QVBoxLayout(col_group)

        load_row = QHBoxLayout()
        load_col_btn = QPushButton("读取列名")
        load_col_btn.clicked.connect(self._load_columns)
        load_row.addWidget(load_col_btn)

        self.col_status = QLabel("尚未读取")
        self.col_status.setStyleSheet(f"color: #888; font-size: {base}px;")
        load_row.addWidget(self.col_status)
        load_row.addStretch()
        col_layout.addLayout(load_row)

        combo_row = QHBoxLayout()
        combo_row.addWidget(QLabel("题目所在列:"))
        self.question_combo = QComboBox()
        self.question_combo.setMinimumWidth(200)
        self.question_combo.currentIndexChanged.connect(self._on_selection_changed)
        combo_row.addWidget(self.question_combo)

        combo_row.addSpacing(20)

        combo_row.addWidget(QLabel("答案所在列:"))
        self.answer_combo = QComboBox()
        self.answer_combo.setMinimumWidth(200)
        self.answer_combo.currentIndexChanged.connect(self._on_selection_changed)
        combo_row.addWidget(self.answer_combo)
        col_layout.addLayout(combo_row)

        layout.addWidget(col_group)

        # ========== 3. 数据预览 ==========
        preview_group = QGroupBox("第三步：预览数据（确认选对了列）")
        preview_group.setMinimumHeight(0)
        preview_layout = QVBoxLayout(preview_group)
        preview_layout.setContentsMargins(12, 8, 12, 8)
        preview_layout.setSpacing(4)

        self.preview_label = QLabel("选择文件并读取列名后，这里会显示前几行数据")
        self.preview_label.setStyleSheet(f"color: #888; font-size: {base}px;")
        preview_layout.addWidget(self.preview_label)

        self.preview_table = QTableWidget()
        self.preview_table.setVisible(False)
        preview_layout.addWidget(self.preview_table, 1)

        layout.addWidget(preview_group, 1)

        # ========== 4. 字体大小 ==========
        font_group = QGroupBox("显示设置")
        font_layout = QHBoxLayout(font_group)

        font_layout.addWidget(QLabel("结果窗口字体大小:"))

        self.font_spin = QSpinBox()
        self.font_spin.setRange(12, 120)
        self.font_spin.setValue(self.font_size)
        self.font_spin.setSuffix(" px")
        self.font_spin.setSingleStep(2)
        self.font_spin.setMinimumWidth(140)
        font_layout.addWidget(self.font_spin)

        font_layout.addStretch()
        layout.addWidget(font_group)

        # ========== 5. 按钮 ==========
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("取消")
        cancel_btn.setFixedWidth(100)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        ok_btn = QPushButton("确定")
        ok_btn.setFixedWidth(100)
        ok_btn.clicked.connect(self._on_ok)
        btn_row.addWidget(ok_btn)

        layout.addLayout(btn_row)

        if self.file_path and os.path.isfile(self.file_path):
            self._load_columns()

    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择题库文件", "",
            "表格文件 (*.xls *.xlsx *.csv);;Excel 文件 (*.xls *.xlsx);;CSV 文件 (*.csv);;所有文件 (*.*)"
        )
        if path:
            self.file_path = path
            self.file_input.setText(path)
            self._load_columns()

    def _load_columns(self):
        path = self.file_input.text().strip()
        if not path or not os.path.isfile(path):
            QMessageBox.warning(self, "错误", "请先选择有效的题库文件")
            return

        try:
            self.headers = QuestionBank.get_columns(path)
            _, self.preview_rows = read_spreadsheet(path)
        except Exception as e:
            QMessageBox.warning(self, "错误", f"读取列名失败:\n{e}")
            self.col_status.setText(f"读取失败: {e}")
            self.col_status.setStyleSheet("color: #ff6b6b; font-size: 30px;")
            return

        if not self.headers:
            QMessageBox.warning(self, "错误", "文件为空或无法读取表头")
            return

        self.question_combo.blockSignals(True)
        self.answer_combo.blockSignals(True)

        self.question_combo.clear()
        self.answer_combo.clear()
        for i, col_name in enumerate(self.headers):
            self.question_combo.addItem(col_name, i)
            self.answer_combo.addItem(col_name, i)

        # 恢复上次选择的列
        if self.question_col < len(self.headers):
            self.question_combo.setCurrentIndex(self.question_col)
        elif len(self.headers) > 1:
            self.question_combo.setCurrentIndex(1)

        if self.answer_col < len(self.headers):
            self.answer_combo.setCurrentIndex(self.answer_col)
        elif len(self.headers) > 2:
            self.answer_combo.setCurrentIndex(2)

        self.question_combo.blockSignals(False)
        self.answer_combo.blockSignals(False)

        self.col_status.setText(f"已读取 {len(self.headers)} 列，共 {len(self.preview_rows)} 行数据")
        self.col_status.setStyleSheet("color: #00FF88; font-size: 30px;")

        self._update_preview()

    def _on_selection_changed(self):
        if self.headers and self.preview_rows:
            self._update_preview()

    def _update_preview(self):
        q_col = self.question_combo.currentData()
        a_col = self.answer_combo.currentData()

        if q_col is None or a_col is None:
            return

        preview = self.preview_rows[:5]
        if not preview:
            self.preview_label.setText("没有数据行")
            return

        self.preview_table.setVisible(True)
        self.preview_label.setText(
            f"题目列: 第{q_col + 1}列 [{self.headers[q_col]}]  |  "
            f"答案列: 第{a_col + 1}列 [{self.headers[a_col]}]  |  "
            f"前 {len(preview)} 行预览:"
        )
        self.preview_label.setStyleSheet("color: #4FC3F7; font-size: 30px;")

        self.preview_table.setColumnCount(2)
        self.preview_table.setHorizontalHeaderLabels(["题目", "答案"])
        self.preview_table.setRowCount(len(preview))

        for r, row in enumerate(preview):
            q_val = row[q_col] if q_col < len(row) else ""
            a_val = row[a_col] if a_col < len(row) else ""
            self.preview_table.setItem(r, 0, QTableWidgetItem(q_val[:80]))
            self.preview_table.setItem(r, 1, QTableWidgetItem(a_val[:80]))

        self.preview_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

    def _on_ok(self):
        path = self.file_input.text().strip()
        if not path or not os.path.isfile(path):
            QMessageBox.warning(self, "错误", "请选择有效的题库文件")
            return

        if self.question_combo.count() == 0:
            QMessageBox.warning(self, "错误", "请先点击「读取列名」")
            return

        self.file_path = path
        self.question_col = self.question_combo.currentData()
        self.answer_col = self.answer_combo.currentData()
        self.font_size = self.font_spin.value()

        if self.question_col == self.answer_col:
            QMessageBox.warning(self, "错误", "题目列和答案列不能相同")
            return

        # 自动保存设置
        save_settings(self.get_settings())

        self.accept()

    def get_settings(self):
        return {
            "path": self.file_path,
            "question_col": self.question_col,
            "answer_col": self.answer_col,
            "font_size": self.font_size,
        }
