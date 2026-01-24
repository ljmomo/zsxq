按照你的要求，我将分两步进行：

### 第一步：代码提交与分支管理
1.  **提交当前更改**：将所有新生成的文档（PRD, Tech Spec）、Skill 配置、新脚本提交到 `main` 分支。
2.  **创建开发分支**：创建并切换到 `feat/desktop-gui` 分支，用于阶段一的桌面端开发。

### 第二步：核心层重构 (Core Refactoring)
根据技术方案，GUI 开发的基础是将核心逻辑与 CLI/UI 解耦。我将优先进行 **Core 层重构**。

**计划任务：**
1.  **创建目录结构**：按照技术文档创建 `src/core`, `src/gui` 等目录。
2.  **封装 ZSXQCore**：
    *   在 `src/core/zsxq_api.py` 中创建 `ZSXQCore` 类。
    *   从 `zsxq_playwright.py` 中迁移并改造以下方法（去除 print/input，改为返回值或回调）：
        *   `__init__` (初始化配置)
        *   `start_browser` (启动浏览器)
        *   `check_login_status` (返回 bool)
        *   `get_subscriptions` (返回列表数据)
        *   `get_files` (滚动获取文件数据)
        *   `download_file` (执行下载)
3.  **验证重构**：编写一个简单的 `main_test.py` 调用 `ZSXQCore`，确保逻辑在无 GUI 环境下跑通。

**注意**：在开发过程中，如果遇到如“是否需要引入新的依赖库”或“API 设计的重大取舍”等无法抉择的问题，我会暂停并向你确认。

现在，我将先执行第一步（Git 操作），然后开始搭建目录结构。