# 阶段一：知识星球下载器桌面版 (MVP) 技术方案

## 1. 技术选型

### 1.1 核心栈
- **语言**：Python 3.10+
- **GUI 框架**：**PySide6** (Qt for Python)
  - *选择理由*：成熟稳定，控件丰富，支持信号槽机制，方便与后端逻辑解耦。相比 Electron，无需引入 Node.js 环境，打包体积更小，且核心逻辑本身就是 Python，调用无缝。
- **浏览器自动化**：**Playwright** (同步 API)
  - *维持现状*：复用现有稳定逻辑，运行在独立线程中避免阻塞 UI。
- **打包工具**：**PyInstaller**
  - *目标*：生成单文件或单目录的 `.exe`。

## 2. 架构设计

采用经典的 **MVC (Model-View-Controller)** 变体：

### 2.1 目录结构
```
src/
├── gui/
│   ├── __init__.py
│   ├── main_window.py    # 主窗口 UI
│   ├── login_dialog.py   # 登录引导对话框
│   └── widgets/          # 自定义组件 (LogPanel, ProgressBar)
├── core/
│   ├── __init__.py
│   ├── zsxq_api.py       # 封装后的核心逻辑类 (ZSXQCore)
│   └── worker.py         # QThread 工作线程，负责执行耗时任务
├── utils/
│   └── logger.py
└── main.py               # 程序入口
```

### 2.2 核心模块设计

#### A. `ZSXQCore` 类 (逻辑层)
将现有的 `zsxq_playwright.py` 重构为一个无状态（或少状态）的 API 类。
- **职责**：只负责浏览器操作，不负责任何打印或交互。
- **方法签名**：
  - `launch_browser()`
  - `check_is_logged_in() -> bool`
  - `get_subscriptions() -> list`
  - `start_download_task(planet_name, save_path, options)`

#### B. `Worker` 线程 (中间层)
由于 Playwright 操作是耗时的（且同步 API 会阻塞线程），必须放入 `QThread` 中运行。
- **信号 (Signals)**：
  - `log_signal(str)`: 发送日志文本到 UI。
  - `progress_signal(int, int)`: 发送 (当前, 总数) 更新进度条。
  - `finished_signal(bool)`: 任务结束。
  - `error_signal(str)`: 发生错误。

#### C. `MainWindow` (视图层)
- **布局**：
  - 左侧 `QListWidget`：展示星球列表。
  - 右侧 `QStackedWidget`：
    - 页 1：欢迎/未选择状态。
    - 页 2：任务配置页（路径选择、开始按钮、Log 输出）。

## 3. 关键流程实现

### 3.1 登录流程
1. 用户点击 GUI “登录”。
2. GUI 触发 `Worker` 调用 `core.launch_browser(headless=False)`。
3. Playwright 启动浏览器窗口（持久化 Context）。
4. 用户在浏览器中扫码。
5. `Worker` 轮询检测 `core.check_is_logged_in()`。
6. 检测成功 -> 发送 `finished_signal` -> GUI 关闭浏览器窗口（或提示用户关闭） -> 刷新星球列表。

### 3.2 下载流程
1. 用户选择星球、路径，点击“开始”。
2. GUI 禁用“开始”按钮，实例化 `DownloadWorker` 线程。
3. `DownloadWorker` 执行：
   - 导航到星球。
   - 滚动采集文件（每采集一批发送 `log_signal`）。
   - 循环下载文件（每下载一个发送 `progress_signal`）。
4. 任务结束 -> 恢复 GUI 按钮状态。

## 4. 打包发布 (Build Pipeline)

### 4.1 PyInstaller 配置
- **Spec 文件**：定义隐式导入（Playwright 依赖）。
- **资源文件**：
  - Playwright 的浏览器二进制文件通常不打包进去（体积太大），而是：
    1. *方案 A*：在软件启动时检测并自动下载浏览器（`playwright install chromium`）。
    2. *方案 B (推荐)*：打包时设法包含 chromium shell，或提示用户安装。
    *注：为了用户体验，建议采用方案 A，在首次启动时有一个“初始化环境”的进度条。*

### 4.2 版本控制
- 使用 `version.txt` 管理版本号。
- GitHub Actions 自动构建 Release。

## 5. 风险与对策
- **UI 卡死**：严格遵守“耗时操作不上主线程”原则。
- **Playwright 依赖**：用户电脑缺少依赖库。
  - *对策*：在错误日志中明确提示，并提供一键修复脚本。
- **反爬/风控**：
  - *对策*：保留现有的随机延迟逻辑；在 GUI 中增加“安全模式”选项（增加间隔）。
