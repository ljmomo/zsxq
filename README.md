# 使用说明书

## 简介
- 本工具用于批量下载「知识星球」某订阅星球的文件，支持持久化登录、滚动加载、交互选择与文件列表打印。

## 环境要求
- 操作系统：Windows
- Python：3.x
- 依赖：playwright
  - 安装依赖：
    - pip install playwright
    - python -m playwright install

## 目录说明
- 下载目录：./downloads/zsxq_files（自动创建）
- 临时目录：./downloads/zsxq_files/temp_cache（下载中间目录，成功后自动清理）
- 登录数据：./browser_data/zsxq（持久化登录态）

## 快速开始
1. 打开并运行主脚本：[zsxq_playwright.py](file:///d:/aicode/zsxq/zsxq_playwright.py)
2. 首次运行需在弹出浏览器中手动登录，随后状态自动保存
3. 程序会打印订阅星球列表（仅 /group），输入序号或名称选择目标星球
4. 自动进入该星球后点击右侧“星球文件”入口
5. 输入滚动次数（确认加载更多文件的次数）
6. 打印所有采集到的文件列表
7. 输入下载数量（回车表示默认值/全部）并开始批量下载
8. 下载完成后临时目录自动清理

## 运行步骤（详细）
- 运行：python d:\aicode\zsxq\zsxq_playwright.py
- 登录：若未登录，按提示在浏览器中完成，然后回车继续
- 选择订阅：根据打印列表输入订阅序号或名称（仅 /group 链接）
  - 相关方法：[list_subscriptions](file:///d:/aicode/zsxq/zsxq_playwright.py#L127-L231) [choose_subscription](file:///d:/aicode/zsxq/zsxq_playwright.py#L255-L270)
- 点击文件入口：[click_files_entry](file:///d:/aicode/zsxq/zsxq_playwright.py#L197-L245)
- 输入滚动次数：控制采集时滚动加载的次数（默认 100 或 main 中配置的 FILES_SCROLL_LIMIT）
  - 相关方法：[prompt_scroll_attempts](file:///d:/aicode/zsxq/zsxq_playwright.py#L661-L673)
- 打印文件列表：[print_files](file:///d:/aicode/zsxq/zsxq_playwright.py#L244-L252)
- 选择下载数量：输入 N 或回车使用默认/全部
  - 相关方法：[prompt_download_count](file:///d:/aicode/zsxq/zsxq_playwright.py#L643-L660)
- 批量下载：坐标点击/JS 点击触发下载，事件监听兜底；若事件未触发则从临时目录中移动稳定文件到目标目录
  - 相关方法：[download_file](file:///d:/aicode/zsxq/zsxq_playwright.py#L510-L744) [wait_for_completed_file](file:///d:/aicode/zsxq/zsxq_playwright.py#L425-L447)

## 配置项
- 在 [main](file:///d:/aicode/zsxq/zsxq_playwright.py#L968-L1005) 中调整：
  - PLANET_NAME：默认目标星球名（当你在订阅选择阶段回车跳过时使用）
  - DOWNLOAD_DIR：下载保存目录
  - USER_DATA_DIR：登录数据目录
  - MAX_FILES：默认下载数量（回车时使用该默认值；为空代表全部）
  - SUBS_SCROLL_LIMIT：订阅列表滚动次数上限
  - FILES_SCROLL_LIMIT：文件列表滚动次数默认值

## 常见问题与解决
- 浏览器无法启动：请关闭所有 Chromium/Chrome 窗口，检查数据目录锁定或以管理员运行
- 未找到“星球文件”：页面结构变化时，使用工具的兜底提示手动点击；随后流程继续
- 下载事件未触发：工具会在临时目录中检测稳定文件并移动到目标目录
- 采集不全：提高滚动次数或延长 pause；订阅采集仅保留 /group 链接，确保你的订阅在该列表中

## 结果与输出
- 成功下载的文件保存在 DOWNLOAD_DIR
- 临时目录在批量下载结束后删除（防止缓存残留）
- 控制台打印：订阅列表、滚动次数确认信息、文件列表、下载进度与统计

## 注意事项
- 该工具依赖页面 DOM 结构，若界面升级需要更新选择器与过滤策略
- 登录数据仅用于本地持久化，不要提交到远程仓库

## 进一步扩展
- 命令行参数支持（非交互）
- 文件类型与关键字过滤
- 时间范围筛选、失败重试与断点续传

