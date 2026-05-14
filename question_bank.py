import re
import csv
import os
from difflib import SequenceMatcher

import xlrd
import openpyxl

from config import QUESTION_BANK_PATH, MATCH_THRESHOLD, MAX_RESULTS


def _read_xls(path):
    """读取 .xls 文件，返回 (headers, rows)"""
    wb = xlrd.open_workbook(path)
    sheet = wb.sheet_by_index(0)
    headers = [str(sheet.cell_value(0, c)).strip() for c in range(sheet.ncols)]
    rows = []
    for r in range(1, sheet.nrows):
        row = [str(sheet.cell_value(r, c)).strip() for c in range(sheet.ncols)]
        rows.append(row)
    return headers, rows


def _read_xlsx(path):
    """读取 .xlsx 文件，返回 (headers, rows)"""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    sheet = wb.active
    rows = list(sheet.iter_rows(values_only=True))
    if not rows:
        return [], []
    headers = [str(c).strip() if c is not None else "" for c in rows[0]]
    data = []
    for row in rows[1:]:
        data.append([str(c).strip() if c is not None else "" for c in row])
    wb.close()
    return headers, data


def _read_csv(path):
    """读取 .csv 文件，返回 (headers, rows)"""
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        rows = list(reader)
    if not rows:
        return [], []
    headers = [c.strip() for c in rows[0]]
    return headers, rows[1:]


def read_spreadsheet(path):
    """根据扩展名自动读取表格文件，返回 (headers, rows)"""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".xls":
        return _read_xls(path)
    elif ext == ".xlsx":
        return _read_xlsx(path)
    elif ext == ".csv":
        return _read_csv(path)
    else:
        # 尝试用 xlrd 打开，再尝试 openpyxl
        try:
            return _read_xls(path)
        except Exception:
            return _read_xlsx(path)


class QuestionBank:
    def __init__(self, path=None, question_col=1, answer_col=2):
        self.path = path or QUESTION_BANK_PATH
        self.question_col = question_col
        self.answer_col = answer_col
        self.questions = []  # [(question, answer), ...]
        self.index = {}      # {keyword: [idx, ...]}
        self._load()

    def _tokenize(self, text):
        """提取关键词：先按标点拆分，再对长中文串提取2-4字滑窗"""
        parts = re.split(r'[^一-鿿\w]+', text)
        keywords = []
        for part in parts:
            if len(part) < 2:
                continue
            if re.match(r'^[a-zA-Z0-9]+$', part):
                keywords.append(part.lower())
                continue
            for n in (3, 2, 4):
                for i in range(len(part) - n + 1):
                    keywords.append(part[i:i+n])
        return keywords

    def _load(self):
        headers, rows = read_spreadsheet(self.path)
        for row in rows:
            if len(row) <= max(self.question_col, self.answer_col):
                continue
            question = row[self.question_col].strip()
            answer = row[self.answer_col].strip()
            if not question:
                continue
            idx = len(self.questions)
            self.questions.append((question, answer))
            for kw in self._tokenize(question):
                self.index.setdefault(kw, []).append(idx)
        print(f"[题库] 加载完成: {len(self.questions)} 道题")

    def match(self, text, threshold=None, max_results=None):
        """对 OCR 文本进行模糊匹配，返回 [(score, question, answer), ...]"""
        if threshold is None:
            threshold = MATCH_THRESHOLD
        if max_results is None:
            max_results = MAX_RESULTS

        keywords = self._tokenize(text)
        if not keywords:
            return []

        candidate_indices = set()
        for kw in keywords:
            for idx in self.index.get(kw, []):
                candidate_indices.add(idx)

        if not candidate_indices:
            candidate_indices = set(range(len(self.questions)))

        results = []
        text_clean = text.replace(" ", "").replace("\n", "")
        for idx in candidate_indices:
            q, a = self.questions[idx]
            q_clean = q.replace(" ", "").replace("\n", "")
            score = SequenceMatcher(None, text_clean, q_clean).ratio()
            if score >= threshold:
                results.append((score, q, a))

        results.sort(key=lambda x: x[0], reverse=True)
        return results[:max_results]

    @staticmethod
    def get_columns(path):
        """读取题库文件的列名（表头行）"""
        headers, _ = read_spreadsheet(path)
        result = []
        for i, h in enumerate(headers):
            if not h:
                result.append(f"第{i + 1}列")
            else:
                result.append(h)
        return result
