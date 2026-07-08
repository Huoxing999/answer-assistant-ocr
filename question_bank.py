import re
import csv
import os
from difflib import SequenceMatcher

import xlrd
import openpyxl

from config import QUESTION_BANK_PATH, MATCH_THRESHOLD, MAX_RESULTS

OPTION_RE = re.compile(
    r'(?P<label>[A-Ha-h])\s*[\.．、:：\)\]）】]?\s*'
    r'(?P<text>.*?)'
    r'(?=(?:\s+[A-Ha-h]\s*[\.．、:：\)\]）】]?\s*)|$)',
    re.S,
)


def clean_text(text):
    """用于匹配的轻量清洗：去掉常见空白。"""
    return re.sub(r'\s+', '', str(text or ""))


def parse_options(*texts):
    """从题库选项、题干或 OCR 文本中提取 A/B/C/D 选项。"""
    options = {}
    protected_labels = set()
    plain_texts = []
    for item in texts:
        if not item:
            continue
        if isinstance(item, dict):
            for label, value in item.items():
                label = str(label or "").strip().upper()
                value = re.sub(r'\s+', ' ', str(value or "")).strip()
                if re.fullmatch(r'[A-H]', label) and value:
                    options[label] = value
                    protected_labels.add(label)
            continue
        plain_texts.append(str(item))

    for plain_text in plain_texts:
        merged = plain_text.replace("\r", "\n")
        for match in OPTION_RE.finditer(merged):
            label = match.group("label").upper()
            value = re.sub(r'\s+', ' ', match.group("text")).strip()
            value = value.strip("。；;，,")
            if not value:
                continue
            if label in options or label in protected_labels:
                continue
            options[label] = value
    return options


def expand_answer_with_options(answer, *texts):
    """把答案字母补全为“字母 + 选项内容”。"""
    _, _, display_text = expand_answer_parts(answer, *texts)
    return display_text


def expand_answer_parts(answer, *texts):
    """返回 (答案字母, [(字母, 选项内容)], 复制/兼容显示文本)。"""
    answer_text = str(answer or "").strip()
    if not answer_text:
        return "", [], answer_text

    options = parse_options(*texts)
    labels = re.findall(r'[A-Ha-h]', answer_text)
    if not labels:
        return answer_text, [], answer_text

    normalized_labels = []
    details = []
    seen = set()
    for raw_label in labels:
        label = raw_label.upper()
        if label in seen:
            continue
        seen.add(label)
        normalized_labels.append(label)
        option_text = options.get(label)
        if option_text:
            details.append((label, option_text))

    answer_code = "".join(normalized_labels) or answer_text
    if not details:
        return answer_code, [], answer_text

    detail_text = "\n".join(f"{label} {text}" for label, text in details)
    return answer_code, details, f"{answer_code}\n{detail_text}"


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
    def __init__(self, path=None, question_col=1, answer_col=2, option_cols=None):
        self.path = path or QUESTION_BANK_PATH
        self.question_col = question_col
        self.answer_col = answer_col
        self.option_cols = self._normalize_option_cols(option_cols)
        self.questions = []  # [(question, answer, question_clean, options), ...]
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
        return list(dict.fromkeys(keywords))

    def _load(self):
        headers, rows = read_spreadsheet(self.path)
        option_cols = self.option_cols or self._detect_option_columns(headers, rows)
        self.option_cols = option_cols
        for row in rows:
            if len(row) <= max(self.question_col, self.answer_col):
                continue
            question = row[self.question_col].strip()
            answer = row[self.answer_col].strip()
            if not question:
                continue
            options = self._row_options(row, option_cols)
            idx = len(self.questions)
            self.questions.append((question, answer, clean_text(question), options))
            for kw in self._tokenize(question):
                self.index.setdefault(kw, []).append(idx)
        print(f"[题库] 加载完成: {len(self.questions)} 道题")

    @staticmethod
    def _normalize_option_cols(option_cols):
        if not option_cols:
            return {}
        normalized = {}
        for label, col in option_cols.items():
            label = str(label or "").strip().upper()
            if not re.fullmatch(r'[A-H]', label):
                continue
            if col is None or col == "":
                continue
            try:
                normalized[label] = int(col)
            except (TypeError, ValueError):
                continue
        return normalized

    @staticmethod
    def detect_columns(headers, rows, question_col=None, answer_col=None):
        """根据表头和样例行猜测题目列、答案列、选项列。"""
        q_col = question_col
        a_col = answer_col

        for idx, header in enumerate(headers):
            normalized = re.sub(r'\s+', '', str(header or "")).upper()
            if q_col is None and any(key in normalized for key in ("题目", "题干", "QUESTION")):
                q_col = idx
            if a_col is None and any(key in normalized for key in ("答案", "正确答案", "ANSWER")):
                a_col = idx

        if q_col is None and rows:
            max_len = -1
            for idx in range(len(headers)):
                samples = [row[idx] for row in rows[:20] if idx < len(row)]
                avg_len = sum(len(str(v or "")) for v in samples) / max(len(samples), 1)
                if avg_len > max_len:
                    max_len = avg_len
                    q_col = idx

        if a_col is None and rows:
            for idx in range(len(headers)):
                if idx == q_col:
                    continue
                samples = [str(row[idx] or "").strip() for row in rows[:20] if idx < len(row)]
                filled = [s for s in samples if s]
                if filled and all(re.fullmatch(r'[A-Ha-h]+', s) for s in filled[:10]):
                    a_col = idx
                    break

        if q_col is None:
            q_col = 1 if len(headers) > 1 else 0
        if a_col is None:
            a_col = 2 if len(headers) > 2 else min(len(headers) - 1, 1)

        option_cols = QuestionBank._detect_option_columns_for(headers, q_col, a_col)
        return q_col, a_col, option_cols

    def _detect_option_columns(self, headers, rows):
        """自动识别选项列，支持“选项A/选项B”表头和题目列到答案列之间的常见布局。"""
        return self._detect_option_columns_for(headers, self.question_col, self.answer_col)

    @staticmethod
    def _detect_option_columns_for(headers, question_col, answer_col):
        option_cols = {}
        for idx, header in enumerate(headers):
            if idx in (question_col, answer_col):
                continue
            normalized = re.sub(r'\s+', '', str(header or "")).upper()
            match = re.search(r'(?:选项|OPTION)?([A-H])$', normalized)
            if match:
                option_cols[match.group(1)] = idx

        if option_cols:
            return option_cols

        start = min(question_col, answer_col) + 1
        end = max(question_col, answer_col)
        between = [idx for idx in range(start, end) if idx not in (question_col, answer_col)]
        labels = "ABCDEFGH"
        if 2 <= len(between) <= len(labels):
            return {labels[i]: col for i, col in enumerate(between)}

        return {}

    def _row_options(self, row, option_cols):
        options = {}
        for label, col in option_cols.items():
            if col >= len(row):
                continue
            value = str(row[col] or "").strip()
            if value:
                options[label] = value
        return options

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
        text_clean = clean_text(text)
        for idx in candidate_indices:
            q, a, q_clean, options = self.questions[idx]
            score = SequenceMatcher(None, text_clean, q_clean).ratio()
            if score >= threshold:
                results.append((score, q, a, options))

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
