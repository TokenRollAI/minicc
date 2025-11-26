# 使用指南

## 安装

```bash
# 使用 uv
uv pip install minicc

# 使用 pip
pip install minicc
```

## 配置 API Key

```bash
# Anthropic
export ANTHROPIC_API_KEY="sk-ant-xxx"

# OpenAI
export OPENAI_API_KEY="sk-xxx"
```

## 启动应用

```bash
# 命令行启动
minicc

# 或使用 Python 模块
python -m minicc
```

## 快捷键

| 快捷键 | 功能 |
|--------|------|
| Enter | 发送消息 |
| Ctrl+C | 退出应用 |
| Ctrl+L | 清屏 |
| Escape | 取消当前操作 |

## 配置文件

### ~/.minicc/config.json

```json
{
  "provider": "anthropic",
  "model": "claude-sonnet-4-20250514",
  "api_key": null
}
```

### ~/.minicc/AGENTS.md

自定义系统提示词，可以修改 Agent 的行为和工具使用策略。

## 编程接口

```python
import asyncio
from minicc import create_agent, MiniCCDeps, load_config

async def main():
    config = load_config()
    agent = create_agent(config)
    deps = MiniCCDeps(config=config, cwd="/path/to/project")

    result = await agent.run("你的问题", deps=deps)
    print(result.data)

asyncio.run(main())
```

## 开发调试

```bash
# 使用 textual 开发模式
uv run textual run --dev minicc.app:MiniCCApp

# 在另一个终端查看日志
textual console
```
