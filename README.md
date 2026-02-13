# 知识星球文件下载器

一个基于 Playwright 的知识星球文件自动下载工具，支持从链接解析并批量下载文件。

## 功能特性

- ✅ **链接解析下载**：从给定的链接中解析并下载文件
- ✅ **智能评论过滤**：自动过滤评论、回复等非书籍内容
- ✅ **智能下载按钮识别**：使用评分系统精确识别下载按钮
- ✅ **文件命名**：使用解析出来的文件名保存
- ✅ **弹窗自动关闭**：多种方式确保弹窗正确关闭
- ✅ **多文件下载**：支持批量下载多个文件
- ✅ **登录状态保存**：无需每次重新登录

## 快速开始

### 1. 安装依赖

```bash
pip install playwright
playwright install chromium
```

### 2. 首次使用（登录）

```bash
python3 zsxq_playwright.py
```

在浏览器中登录知识星球，然后关闭浏览器。

### 3. 使用链接解析模式

```bash
# 创建链接配置文件
echo "https://wx.zsxq.com/group/xxx/topic/xxx" > links.txt

# 运行程序
python3 zsxq_playwright.py --mode links --links-file ./links.txt
```

## 使用方式

### 命令行参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--mode` | 运行模式（files/links/both） | `files` |
| `--links-file` | 链接列表文件路径 | `./links.txt` |
| `--download-dir` | 下载目录 | `./downloads` |
| `--max-links` | 最大处理链接数 | 无限制 |

### 运行模式

| 模式 | 说明 |
|------|------|
| `files` | 星球文件下载模式（默认） |
| `links` | 链接解析下载模式 |
| `both` | 同时执行两种模式 |

### 示例

```bash
# 星球文件下载模式（默认）
python3 zsxq_playwright.py

# 链接解析模式
python3 zsxq_playwright.py --mode links

# 指定链接文件和下载目录
python3 zsxq_playwright.py --mode links --links-file ./my_links.txt --download-dir ./my_downloads

# 限制处理链接数
python3 zsxq_playwright.py --mode links --max-links 10
```

## 文档

- [需求文档](docs/REQUIREMENTS.md)
- [技术方案文档](docs/TECHNICAL.md)
- [使用文档](docs/USAGE.md)

## 核心流程

```
初始页面 → 提取书籍列表(过滤评论) → 导航到详情页 
→ 提取附件(过滤评论) → 点击附件 → 智能评分找下载按钮 
→ 点击下载 → 使用解析的文件名保存 → 关闭弹窗 → 返回初始页面
```

## 支持的文件类型

- `.mp3` - 音频文件
- `.doc` - Word 文档
- `.docx` - Word 文档

## 项目结构

```
zsxq/
├── zsxq_playwright.py      # 主程序
├── test_detailed_flow.py   # 测试脚本
├── links.txt               # 链接配置文件
├── browser_data/           # 浏览器数据目录
├── downloads/              # 下载目录
└── docs/                   # 文档目录
    ├── REQUIREMENTS.md     # 需求文档
    ├── TECHNICAL.md        # 技术方案文档
    └── USAGE.md            # 使用文档
```

## 常见问题

### 登录问题

如果提示"请先登录知识星球"：

```bash
# 删除浏览器数据目录
rm -rf ./browser_data

# 重新运行程序并登录
python3 zsxq_playwright.py
```

### 下载失败

1. 检查网络连接
2. 检查登录状态
3. 查看控制台错误信息

## 注意事项

1. **首次使用**：需要在浏览器中登录知识星球
2. **登录状态**：系统会保存登录状态，下次无需重新登录
3. **下载目录**：文件会保存到指定的下载目录
4. **等待时间**：系统会自动等待页面加载和下载完成
5. **错误处理**：如果某个步骤失败，系统会继续处理下一个

## 许可证

MIT License

## 更新日志

### v1.0.0 (2024-02-13)

- 新增链接解析下载模式
- 新增评论过滤功能
- 新增智能下载按钮识别
- 新增文件命名功能
- 新增弹窗自动关闭
- 新增多文件下载支持
