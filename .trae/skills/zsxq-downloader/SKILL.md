---
name: "zsxq-downloader"
description: "批量下载知识星球（ZSXQ）文件。当用户想要从订阅的星球下载文件时调用。"
---

# 知识星球下载器 Skill

该 Skill 允许你使用本地 Python 脚本从指定的知识星球订阅中批量下载文件。

## 前置条件
- 工作区根目录下必须存在脚本 `zsxq_skill_runner.py`。
- Python 环境已安装 `playwright`。
- 用户必须已登录（浏览器数据持久化在 `./browser_data/zsxq`）。

## 使用方法

要使用此 Skill，请使用 `RunCommand` 工具执行 Python 脚本并传入适当参数。

### 参数
- `--planet`: (必填) 要下载的星球名称。
- `--max-files`: (可选) 最大下载文件数。默认值：10。
- `--subs-scroll`: (可选) 订阅列表滚动尝试次数。默认值：20。
- `--files-scroll`: (可选) 文件列表滚动尝试次数。默认值：100。
- `--non-interactive`: (推荐) 以非交互模式运行，适合自动化执行。

### 示例命令

```bash
python zsxq_skill_runner.py --planet "目标星球名称" --max-files 50 --non-interactive
```

## 行为
1. 脚本将启动浏览器（可见模式）以复用登录会话。
2. 导航至指定的星球。
3. 滚动查找文件并将其下载到 `./downloads/zsxq_files`。
4. 临时文件会自动清理。
