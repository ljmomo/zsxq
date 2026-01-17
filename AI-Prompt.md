# AI 编程 Prompt（可直接用于代码生成与迭代）

## 角色设定
- 你是一位资深 Python 自动化工程师，精通 Playwright 与浏览器自动化，能在 Windows 环境下编写稳健、可维护的代码。

## 项目目标
- 在已登录状态下，批量下载「知识星球」订阅星球的文件。
- 支持订阅列表采集与交互选择（仅 /group 链接）、滚动加载文件、打印文件列表、下载数量限制、临时目录清理。

## 环境与约束
- 操作系统：Windows
- 语言与框架：Python 3.x + Playwright（同步 API）
- 浏览器：Chromium 持久化上下文
- 路径约束：工作目录 d:\aicode\zsxq；下载目录 ./downloads/zsxq_files；登录数据目录 ./browser_data/zsxq
- 安全约束：不得输出或写入任何敏感信息；不要提交登录态到远端；禁止日志中泄露隐私数据。
- 代码风格：模块化、函数清晰命名、交互文案简洁中文；保持现有结构与命名一致。

## 现有核心实现参考
- 持久化上下文与登录检测 [start_browser](file:///d:/aicode/zsxq/zsxq_playwright.py#L33-L68) [check_login_status](file:///d:/aicode/zsxq/zsxq_playwright.py#L77-L112)
- 订阅采集（仅 a[href*="/group"]）、打印、交互选择、打开订阅 [list_subscriptions](file:///d:/aicode/zsxq/zsxq_playwright.py#L127-L231) [print_subscriptions](file:///d:/aicode/zsxq/zsxq_playwright.py#L244-L252) [choose_subscription](file:///d:/aicode/zsxq/zsxq_playwright.py#L255-L270) [open_subscription](file:///d:/aicode/zsxq/zsxq_playwright.py#L272-L285)
- 点击“星球文件”入口（多策略与兜底） [click_files_entry](file:///d:/aicode/zsxq/zsxq_playwright.py#L197-L245)
- 文件提取与滚动加载 [get_file_elements](file:///d:/aicode/zsxq/zsxq_playwright.py#L246-L329) [load_all_files](file:///d:/aicode/zsxq/zsxq_playwright.py#L330-L379)
- 打印所有文件列表 [print_files](file:///d:/aicode/zsxq/zsxq_playwright.py#L244-L252)
- 下载按钮智能定位与事件兜底 [download_file](file:///d:/aicode/zsxq/zsxq_playwright.py#L510-L744) [_wait_for_completed_file](file:///d:/aicode/zsxq/zsxq_playwright.py#L425-L447)
- 临时目录清理 [_remove_temp_dir](file:///d:/aicode/zsxq/zsxq_playwright.py#L662-L669)
- 主流程编排 [download_all](file:///d:/aicode/zsxq/zsxq_playwright.py#L906-L941)；入口配置 [main](file:///d:/aicode/zsxq/zsxq_playwright.py#L968-L1005)

## 必须满足的功能与交互
- 启动浏览器：launch_persistent_context，headless=False，downloads_path 指向 ./downloads/zsxq_files/temp_cache，accept_downloads=True，窗口最大化，locale=zh-CN。
- 登录状态：已登录则复用状态，否则提示用户登录并回车继续。
- 订阅列表：
  - 仅收集 a[href*="/group"]，过滤“发现/优质/推荐”等非订阅内容，限定在侧栏/导航区域。
  - 打印订阅列表，支持输入序号或名称选择；若用户回车则使用默认 PLANET_NAME。
- 文件入口：点击右侧“星球文件”，支持多选择器策略，失败提供手动点击兜底提示。
- 滚动次数确认：输入确认滚动次数（默认值来自 FILES_SCROLL_LIMIT 或 100），按该次数滚动加载文件列表。
- 文件列表打印：打印采集到的全部文件名。
- 下载数量确认：输入 N 或回车使用默认值（MAX_FILES 或全部）。
- 下载执行：
  - 智能评分定位“下载”按钮（文本=下载、可见与尺寸、cursor=pointer、位置分）。
  - 坐标点击与 JS 点击双策略；监听下载事件。若未触发，临时目录检测稳定文件并移动保存。
  - 文件名非法字符清理后保存；删除下载源文件与临时目录缓存。
- 统计与清理：打印成功统计，删除 ./downloads/zsxq_files/temp_cache。

## 关键函数签名（保持一致）
- class ZSXQDownloader(download_dir, user_data_dir)
- start_browser()
- navigate_to_home()
- check_login_status() -> bool
- wait_for_login()
- list_subscriptions(max_scroll_attempts=20, scroll_px=600, pause=0.8) -> list[dict]
- print_subscriptions(subs: list[dict]) -> None
- choose_subscription(subs: list[dict]) -> dict | None
- open_subscription(sub: dict) -> None
- click_files_entry() -> None
- get_file_elements() -> list[dict]
- load_all_files(max_scroll_attempts=100, scroll_px=800, pause=0.8, stable_limit=5) -> list[dict]
- print_files(files: list[dict]) -> None
- download_file(file_obj: dict, index: int) -> bool
- _wait_for_completed_file(timeout=60) -> Optional[Path]
- _cleanup_temp() -> int
- _remove_temp_dir() -> None
- download_all(planet_name, max_files=None, subs_scroll_limit=None, files_scroll_limit=None) -> None
- close()

## 验收标准
- 运行 d:\aicode\zsxq\zsxq_playwright.py，完成：打印订阅列表→选择订阅→点击“星球文件”→确认滚动次数→打印文件列表→确认下载数量→完成下载→清理临时目录。
- 编译通过：python -m py_compile d:\aicode\zsxq\zsxq_playwright.py
- 代码遵守约束：无敏感信息输出、可读性与模块化良好、交互信息中文且简洁。
- 异常兜底：入口定位失败可手动继续；下载事件未触发仍能从临时目录保存文件。

## 迭代建议（可选）
- 将交互改为 CLI 参数支持（非交互批处理）。
- 增加文件类型与关键字过滤；时间范围筛选。
- 失败重试与断点续传；更健壮的选择器策略。

## 运行入口约定
- main 中暴露可配置项：PLANET_NAME、DOWNLOAD_DIR、USER_DATA_DIR、MAX_FILES、SUBS_SCROLL_LIMIT、FILES_SCROLL_LIMIT、DEBUG_MODE
- 运行后按交互提示完成流程并输出结果。
