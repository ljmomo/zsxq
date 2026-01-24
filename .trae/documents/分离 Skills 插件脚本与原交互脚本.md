将 Skills 插件逻辑与原脚本分离，恢复原脚本的交互功能，并创建一个专用的 Skill 运行脚本。

具体步骤：
1.  **创建专用脚本**：将当前已支持 CLI 和非交互模式的 `zsxq_playwright.py` 复制一份命名为 `zsxq_skill_runner.py`，作为 Skills 插件的专用执行入口。
2.  **恢复原脚本**：将 `zsxq_playwright.py` 回滚到修改前的状态（移除 `argparse` 命令行参数解析、移除 `non-interactive` 判断），保留其作为手动交互工具的纯粹性（使用 `input()` 进行交互）。
3.  **更新 Skill 定义**：修改 `.trae/skills/zsxq-downloader/SKILL.md`，将其调用的命令指向新的 `zsxq_skill_runner.py`。

这样既保留了你习惯的交互式脚本，又拥有了专为 AI 调用的独立插件脚本。