# MiniCC

极简版 Claude Code，用于教学。

**想知道 Claude Code 这类 AI 编程助手是怎么实现的？** 看这个项目就够了。核心代码约 1400 行，架构清晰，注释充分。

## 能干嘛

- 读写文件、搜索代码、执行 shell 命令
- 创建子任务并行处理
- 终端 UI 界面，支持流式输出

## 技术栈

- [pydantic-ai](https://ai.pydantic.dev/) - Agent 框架
- [Textual](https://textual.textualize.io/) - TUI 框架

## 快速开始

```bash
# 安装
uv pip install minicc

# 设置 API Key
export ANTHROPIC_API_KEY="your-key"
# 或 export OPENAI_API_KEY="your-key"

# 运行
minicc
```

## 开发

```bash
git clone https://github.com/user/minicc.git
cd minicc
uv sync
uv run python -m minicc
```

## 项目结构

```
minicc/
├── app.py       # TUI 主程序
├── agent.py     # Agent 定义
├── tools.py     # 工具实现 (文件操作、搜索、bash)
├── config.py    # 配置管理
├── schemas.py   # 数据模型
└── ui/          # UI 组件
```

## 配置

配置文件在 `~/.minicc/config.json`：

```json
{
  "provider": "anthropic",
  "model": "claude-sonnet-4-20250514"
}
```

## 工具列表

| 工具 | 作用 |
|------|------|
| read_file | 读文件 |
| write_file | 写文件 |
| update_file | 改文件 |
| search_files | 按模式搜索文件 |
| grep | 正则搜索内容 |
| bash | 执行命令 |
| spawn_agent | 创建子任务 |

## License

MIT
