将当前脚本转化为 Skills 插件，主要分为两个阶段：
1. **代码改造（适配自动化调用）**：
   - 引入 `argparse` 库，支持通过命令行参数传入星球名称、下载数量、滚动次数等配置。
   - 增加 `--non-interactive` 标志，在 Skill 调用时跳过所有 `input()` 确认环节（如登录确认、下载数确认），直接使用参数或默认值。
   - 调整 `download_all` 逻辑，适配无交互模式。

2. **创建 Skill 插件**：
   - 使用 Trae 内置的 `skill-creator` 工具。
   - 生成 `skill.json` 配置文件，定义工具名称（如 `zsxq-downloader`）、描述及输入参数（planet_name, max_files 等）。
   - 验证生成的插件结构。

### 具体计划步骤
1. 修改 `zsxq_playwright.py`，添加 CLI 参数解析支持。
2. 调用 `skill-creator` 工具，自动生成插件配置。
3. 验证插件生成结果。