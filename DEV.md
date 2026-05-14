# 答题参考助手 - 开发文档

## 项目概述

基于 OCR 的实时答题参考工具。用户框选屏幕上的题目区域，程序自动识别文字并从题库中模糊匹配答案，支持自动复制最佳答案到剪贴板。

- **仓库**: https://github.com/Huoxing999/answer-assistant-ocr
- **技术栈**: Python 3.8+ / PyQt5 / Tesseract OCR / Pillow
- **平台**: Windows 10/11、Linux

---

## 目录结构

```
answer_assistant/
├── main.py              # 程序入口，组装所有组件
├── config.py            # 全局配置常量，Tesseract 路径查找
├── capture.py           # 屏幕截图 + 感知哈希变化检测
├── ocr_engine.py        # 图像预处理管线 + Tesseract OCR 封装
├── question_bank.py     # 电子表格读取 + 倒排索引 + 模糊匹配
├── overlay.py           # PyQt5 窗口组件（识别框 + 结果窗口 + 答案标签）
├── settings_dialog.py   # 设置对话框 + JSON 持久化
├── app_icon.ico         # 程序图标（256x256 透明背景）
├── requirements.txt     # Python 依赖
├── .gitignore
├── README.md            # 用户文档
├── DEV.md               # 本文件（开发文档）
└── .github/workflows/
    └── build.yml        # GitHub Actions 自动构建 Linux AppImage
```

---

## 模块详解

### 1. config.py - 全局配置

**路径查找函数:**

- `_get_base_dir()` - 返回程序根目录。检测 `sys.frozen`（PyInstaller 打包模式），否则用 `__file__` 所在目录。
- `_find_tesseract()` - 多策略查找 Tesseract 可执行文件：
  1. `TESSERACT_CMD` 环境变量
  2. `<base_dir>/Tesseract-OCR/tesseract.exe`（懒人包内嵌）
  3. `<parent_dir>/Tesseract-OCR/tesseract.exe`（上级目录）
  4. Windows: `C:\Program Files\Tesseract-OCR\tesseract.exe`
  5. Linux/macOS: `shutil.which("tesseract")`

**配置常量:**

| 常量 | 默认值 | 说明 |
|------|--------|------|
| `QUESTION_BANK_PATH` | `""` | 默认题库路径（空=运行时选择） |
| `TESSERACT_CMD` | 自动查找 | Tesseract 可执行文件路径 |
| `TESSERACT_LANG` | `"chi_sim+eng"` | OCR 语言（简体中文+英文） |
| `POLL_INTERVAL` | `0.5` | 截图轮询间隔（秒） |
| `CHANGE_THRESHOLD` | `2` | pHash 变化阈值（汉明距离比特数） |
| `MATCH_THRESHOLD` | `0.35` | 匹配相似度下限（SequenceMatcher ratio） |
| `MAX_RESULTS` | `3` | 最大显示结果数 |
| `WINDOW_OPACITY` | `0.6` | 窗口透明度 |
| `WINDOW_MIN_WIDTH` | `800` | 结果窗口最小宽度 |
| `WINDOW_MIN_HEIGHT` | `20` | 结果窗口最小高度 |
| `FONT_SIZE` | `25` | 默认字体大小（px） |

---

### 2. capture.py - 屏幕截图与变化检测

**函数:**

| 函数 | 签名 | 说明 |
|------|------|------|
| `capture_region` | `(screen: QScreen, x, y, w, h) -> PIL.Image` | 使用 `QScreen.grabWindow()` 截取区域，QPixmap → PNG → PIL RGB |
| `compute_hash` | `(image: PIL.Image, hash_size=16) -> int` | 感知哈希（pHash）：灰度→缩放到 16x16→计算均值→生成 256-bit 整数 |
| `hamming_distance` | `(h1: int, h2: int) -> int` | 两个哈希的汉明距离（`x &= x-1` 位计数） |
| `has_changed` | `(prev_hash, current_image) -> bool` | 若 `prev_hash` 为 None 或汉明距离 > `CHANGE_THRESHOLD` 则返回 True |

**设计要点:**
- pHash 对亮度、对比度、缩放变化有鲁棒性，但对文字内容变化很敏感
- 2-bit 阈值非常灵敏，能检测到单个字符的变化

---

### 3. ocr_engine.py - OCR 预处理与识别

**模块级配置:**
- `TESSERACT_CONFIG = "--oem 1 --psm 6"`（LSTM 引擎，统一分块模式）
- `SCALE_FACTOR = 2`（2 倍放大，模拟 300 DPI）

**预处理管线 (`preprocess`):**

```
原始图像
  → 2x 放大（LANCZOS 重采样）
  → 灰度化（"L" 模式）
  → 自动对比度增强（autocontrast, cutoff=1%）
  → 中值滤波去噪（MedianFilter, size=3）
  → 锐化（SHARPEN）
  → Otsu 自适应二值化
  → 二值图像
```

**函数:**

| 函数 | 签名 | 说明 |
|------|------|------|
| `_otsu_threshold` | `(gray_image: PIL.Image) -> int` | 纯 PIL 实现 Otsu 方法，遍历 256 个阈值取最大类间方差 |
| `preprocess` | `(image: PIL.Image) -> PIL.Image` | 完整预处理管线，返回二值图像 |
| `recognize` | `(image: PIL.Image) -> str` | 预处理 + Tesseract 识别，返回去空白文本 |
| `recognize_with_debug` | `(image, debug_path=None) -> str` | 同上，可选保存预处理后图像用于调试 |

**调优要点:**
- 如果 OCR 识别率低，先检查 `debug/` 目录下的预处理图像
- `SCALE_FACTOR` 影响小字识别率，过大会变慢
- `--psm 6` 假设文字是统一分块，如果题目是单行可用 `--psm 7`

---

### 4. question_bank.py - 题库加载与匹配

**电子表格读取:**

| 函数 | 支持格式 | 说明 |
|------|----------|------|
| `_read_xls(path)` | .xls | 使用 `xlrd`，读取 Sheet 0 |
| `_read_xlsx(path)` | .xlsx | 使用 `openpyxl`（read_only + data_only） |
| `_read_csv(path)` | .csv | Python `csv.reader`，utf-8-sig 编码 |
| `read_spreadsheet(path)` | 自动检测 | 按扩展名分发，未知格式依次尝试 |

**`QuestionBank` 类:**

```python
class QuestionBank:
    def __init__(self, path=None, question_col=1, answer_col=2)
    def _tokenize(self, text) -> list[str]      # 关键词提取
    def _load(self)                              # 加载题库，构建倒排索引
    def match(self, text, threshold=None, max_results=None) -> list[tuple]
    def get_columns(path) -> list[str]           # 静态方法，读取表头
```

**分词策略 (`_tokenize`):**
1. 按非中文、非单词字符切分（正则 `[^一-鿿\w]+`）
2. 过滤单字符片段
3. 纯 ASCII/字母数字 → 小写后直接使用
4. 中文字符串 → 滑动窗口 n-gram（优先 3-gram，其次 2-gram、4-gram）

**匹配流程 (`match`):**
1. 对 OCR 文本分词
2. 倒排索引查找候选题目索引（关键词并集）
3. 无候选时回退到全量扫描
4. 对每个候选计算 `SequenceMatcher.ratio()`（去除空格换行后）
5. 过滤阈值（默认 0.35），降序排列，返回 top-N

**性能:**
- 倒排索引将 SequenceMatcher 调用量从 O(N) 降到 O(candidates)
- 900+ 题库匹配耗时约 10-50ms

---

### 5. overlay.py - PyQt5 窗口组件

**类继承关系:**
```
QWidget
├── CaptureRegion    # 识别框（透明覆盖层）
└── ResultWindow     # 结果窗口（题目 + 答案）

QLabel
└── AnswerLabel      # 可点击答案标签
```

#### AnswerLabel

- 左键点击 → 发射 `clicked(str)` 信号 + 复制文本到剪贴板
- 样式：蓝色背景、白色文字、圆角、悬停高亮
- `set_font_size(size)` 动态更新字体

#### CaptureRegion

**属性:**
- `poll_timer: QTimer` - 轮询定时器（间隔 `POLL_INTERVAL`）
- `_locked: bool` - 锁定状态
- `_locked_rect: QRect` - 锁定时的矩形区域
- `_edge_margin: int = 12` - 边缘拖拽检测范围（px）
- `_dragging / _resizing: bool` - 拖拽/缩放状态

**信号:**
- `open_settings = pyqtSignal()` - 右键菜单"题库设置"触发

**方法:**

| 方法 | 说明 |
|------|------|
| `lock()` | 锁定选框，冻结几何位置，光标变箭头 |
| `unlock()` | 解锁，恢复拖拽/缩放 |
| `is_locked() -> bool` | 返回锁定状态 |
| `get_capture_rect() -> QRect` | 返回锁定区域或当前几何 |

**鼠标交互:**
- `_get_resize_edge(pos)` - 检测鼠标在哪个边缘/角落（8 方向 + 内部）
- 内部拖拽 → 移动窗口
- 边缘拖拽 → 缩放窗口
- 8 种光标：`SizeFDiagCursor`、`SizeBDiagCursor`、`SizeHorCursor`、`SizeVerCursor`

**绘制:**
- 半透明暗色背景
- 绿色边框（解锁）/ 蓝色边框（锁定）
- 黄色角标记
- 居中提示文字

**右键菜单:**
- 锁定选框（开始识别）/ 解锁选框
- 题库设置（发射 `open_settings` 信号）
- 退出

#### ResultWindow

**布局:**
```
┌─────────────────────────────────────────────┐
│  识别题目          │  参考答案                │
│  ┌──────────────┐  │  ┌────────────────────┐ │
│  │              │  │  │ 匹配度 95% | 题目..│ │
│  │  题目文字     │  │  │ 答案A              │ │
│  │              │  │  │ 匹配度 80% | 题目..│ │
│  │              │  │  │ 答案B              │ │
│  │              │  │  │                    │ │
│  └──────────────┘  │  │ [已自动复制最佳答案] │ │
│                    │  └────────────────────┘ │
└─────────────────────────────────────────────┘
```

**方法:**

| 方法 | 说明 |
|------|------|
| `update_question(text)` | 更新题目文字 |
| `update_answers(results)` | 清空旧答案，重建答案列表，自动复制最佳答案 |
| `set_font_size(size)` | 更新字体大小，刷新所有 AnswerLabel |

**自动复制逻辑:**
- `update_answers` 中，第一个结果的 answer 自动通过 `QApplication.clipboard().setText()` 复制
- 状态栏显示"已自动复制最佳答案"（2 秒后清除）

**右键菜单:**
- 字体大小子菜单（20/28/36/48/60/72/84 px）
- 退出

---

### 6. settings_dialog.py - 设置对话框

**持久化函数:**

| 函数 | 说明 |
|------|------|
| `_get_settings_file() -> str` | 返回 `settings.json` 路径（跟随 exe 或脚本目录） |
| `load_settings() -> dict` | 读取 JSON，与默认值合并 |
| `save_settings(settings)` | 写入 JSON（`ensure_ascii=False, indent=2`） |

**SettingsDialog UI 区域:**
1. **选择文件** - QLineEdit + 浏览按钮
2. **选择列** - "读取列名"按钮 + 两个 QComboBox（题目列、答案列）
3. **数据预览** - QTableWidget 显示前 5 行
4. **显示设置** - QSpinBox 字体大小（12-120 px）
5. **按钮** - 取消 + 确定

**自动保存:** 点击确定时自动调用 `save_settings()`

**样式:** 暗色主题（`#1e1e1e` 背景，`#FFD700` 金色标题，`#0078D7` 蓝色按钮），基础字体 30px

---

### 7. main.py - 程序入口

**启动流程:**
```
检查依赖（Tesseract）
  → 创建 QApplication
  → 设置程序图标
  → 加载上次设置
  → 打开设置对话框
  → 加载题库（QuestionBank）
  → 创建 CaptureRegion + ResultWindow
  → 连接信号/槽
  → 启动轮询定时器
  → 进入事件循环
```

**核心轮询函数 `on_poll()`:**
```
每 500ms 触发一次
  → 检查是否锁定
  → 截取屏幕区域
  → pHash 变化检测（跳过未变化）
  → OCR 识别
  → 文本长度检查（< 3 字符跳过）
  → 去重检查（与上次相同跳过）
  → 题库模糊匹配
  → 更新结果窗口 + 自动复制最佳答案
```

**状态管理（闭包变量用列表包裹以支持赋值）:**
- `prev_hash = [None]` - 上次 pHash
- `poll_count = [0]` - 轮询计数
- `last_text = [""]` - 上次 OCR 文本
- `qb_ref = [qb]` - 当前题库实例（设置变更时替换）

**设置变更处理 `_open_settings()`:**
- 临时解锁识别框
- 打开设置对话框
- 若题库路径或列变更 → 重建 QuestionBank，重置状态
- 更新字体大小

---

## 信号/槽连接总览

| 信号 | 来源 | 目标 | 用途 |
|------|------|------|------|
| `poll_timer.timeout` | QTimer (500ms) | `on_poll()` | 周期性截图-OCR-匹配 |
| `open_settings` | CaptureRegion | `_open_settings()` | 重新打开设置 |
| `AnswerLabel.clicked` | AnswerLabel | `ResultWindow._on_copied()` | 点击复制答案 |
| `browse_btn.clicked` | QPushButton | `SettingsDialog._browse_file()` | 选择文件 |
| `load_col_btn.clicked` | QPushButton | `SettingsDialog._load_columns()` | 读取列名 |
| `question_combo.currentIndexChanged` | QComboBox | `_on_selection_changed()` | 刷新预览 |
| `answer_combo.currentIndexChanged` | QComboBox | `_on_selection_changed()` | 刷新预览 |
| `ok_btn.clicked` | QPushButton | `_on_ok()` | 验证并确定 |
| `cancel_btn.clicked` | QPushButton | `reject()` | 取消 |
| 右键菜单动作 | CaptureRegion | `lock()/unlock()/quit` | 区域控制 |
| 右键菜单动作 | ResultWindow | `set_font_size()/quit` | 字体和退出 |

---

## 完整数据流

```
屏幕区域 (QScreen.grabWindow)
       │
       ▼
  capture_region() ──→ PIL.Image (RGB)
       │
       ▼
  has_changed() ←── compute_hash() + hamming_distance()
       │               （pHash 差异 ≤ 2 bit 则跳过 OCR）
       ▼
  recognize()
       │
       ├── preprocess()
       │     1. 2x 放大 (LANCZOS)
       │     2. 灰度化
       │     3. 自动对比度
       │     4. 中值滤波去噪
       │     5. 锐化
       │     6. Otsu 二值化
       │
       └── pytesseract.image_to_string()
             (OEM 1 LSTM, PSM 6, chi_sim+eng)
       │
       ▼
  OCR 文本
       │
       ├── 跳过：长度 < 3（可选保存调试图像）
       ├── 跳过：与上次相同
       │
       ▼
  QuestionBank.match(text)
       │
       ├── _tokenize() → 关键词（中文 n-gram + 英文 token）
       ├── 倒排索引查找 → 候选索引
       ├── SequenceMatcher.ratio() 逐个计算
       ├── 阈值过滤 (0.35)，降序排列，取 top 3
       │
       ▼
  ResultWindow.update_answers(results)
       │
       ├── 显示题目 + 匹配答案及分数
       └── 自动复制最佳答案到剪贴板
```

---

## 构建与打包

### 依赖

```
PyQt5>=5.15        # GUI 框架
pytesseract>=0.3   # Tesseract Python 封装
Pillow>=9.0        # 图像处理
xlrd>=2.0          # 读取 .xls
openpyxl>=3.0      # 读取 .xlsx（requirements.txt 中缺失，需补充）
```

### Windows 懒人包

打包脚本位于 `answer_assistant_portable/build.py`：

1. PyInstaller `--onefile --windowed` 打包为单个 exe
2. 复制 Tesseract-OCR（tesseract.exe + DLL + tessdata）
3. 生成 `使用说明.txt`
4. 输出到 `dist/` 目录

运行：`python build.py`

### Linux AppImage

GitHub Actions 自动构建（`.github/workflows/build.yml`）：

- **触发条件**: push `v*` 标签
- **环境**: Ubuntu 22.04
- **流程**: PyInstaller 打包 → 打包 Tesseract + 语言包 → linuxdeploy 生成 AppImage
- **产物**: `answer-assistant-linux-x86_64.AppImage`

手动触发构建：
```bash
git tag v1.x.x
git push origin v1.x.x
```

---

## PyInstaller 注意事项

程序在打包后需要特殊处理路径：

```python
# 检测是否在打包环境
if getattr(sys, 'frozen', False):
    base_dir = os.path.dirname(sys.executable)      # exe 所在目录
    resource_dir = sys._MEIPASS                      # 临时解压目录（图标等）
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))
```

涉及文件：
- `config.py` - `_get_base_dir()` 和 `_find_tesseract()`
- `settings_dialog.py` - `_get_settings_file()`
- `main.py` - 图标路径

---

## 性能优化策略

| 优化 | 位置 | 说明 |
|------|------|------|
| 感知哈希变化检测 | `capture.py` | 避免对未变化画面执行 OCR（最有效的优化） |
| 文本去重 | `main.py: on_poll()` | `text == last_text` 跳过重复匹配 |
| 倒排索引 | `question_bank.py` | 将匹配候选集从全量缩小到关键词交集 |
| Otsu 自适应二值化 | `ocr_engine.py` | 纯 PIL 实现，无 OpenCV 依赖 |

**瓶颈:** Tesseract OCR 是 CPU 密集型操作，单次识别约 100-500ms。所有操作在主线程执行，轮询间隔 500ms。

---

## 调试方法

### OCR 调试

`main.py` 中 `DEBUG_OCR = True` 时，OCR 失败（文本太短）会保存预处理图像到 `debug/` 目录：

```python
debug_path = os.path.join(DEBUG_DIR, f"debug_{poll_count}.png")
recognize_with_debug(img, debug_path)
```

检查二值化图像可以判断：
- 文字是否清晰可辨
- 二值化阈值是否合适
- 是否有噪点干扰

### 日志输出

程序通过 `print()` 输出运行日志：
- `[启动]` - 初始化信息
- `[轮询#N]` - 每 10 次轮询输出区域坐标
- `[OCR识别]` - 识别到的文字
- `[匹配]` - 匹配结果数
- `[OCR错误]` / `[截图错误]` - 错误信息
- `[设置]` - 题库切换信息

---

## 已知问题与改进方向

### 已知问题

1. **主线程阻塞**: OCR 在主线程执行，识别时界面会短暂卡顿
2. **requirements.txt 缺失 openpyxl**: 需补充 `openpyxl>=3.0`
3. **线程模型**: 所有操作同步执行，大题库首次加载可能较慢

### 可能的改进

| 方向 | 说明 |
|------|------|
| 异步 OCR | 将 Tesseract 调用移到 QThread，避免界面卡顿 |
| OCR 引擎切换 | 支持 PaddleOCR、EasyOCR 等离线引擎，识别率可能更高 |
| 多题库支持 | 同时加载多个题库文件 |
| 历史记录 | 保存识别历史，支持回看 |
| 题库在线更新 | 支持从 URL 下载题库 |
| 截图热键 | 全局快捷键触发截图识别 |
| 结果窗口布局选项 | 支持纵向排列、紧凑模式等 |
| 多语言 UI | 界面国际化 |

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0.0 | 2026-05-14 | Windows 懒人包发布，含全部功能 |
| v1.1.0 | 2026-05-14 | 新增 Linux AppImage 自动构建 |

---

## 发版流程

1. 修改代码并提交
2. 更新版本号（如有必要）
3. 打标签并推送触发构建：
   ```bash
   git tag v1.x.0
   git push origin v1.x.0
   ```
4. GitHub Actions 自动构建 Linux AppImage 并上传到 Release
5. Windows 懒人包需本地构建：
   ```bash
   cd answer_assistant_portable
   python build.py
   ```
6. 将 `dist/` 内容打包为 zip，手动上传到 Release
