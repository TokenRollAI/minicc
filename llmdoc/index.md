# MiniCC 文档索引

极简教学版 AI 编程助手，约 1400 行代码实现核心功能。

## 快速导航

| 文档类型 | 路径 | 说明 |
|---------|------|------|
| 概述 | [/llmdoc/overview/](./overview/) | 项目背景、设计目标、技术选型 |
| 指南 | [/llmdoc/guides/](./guides/) | 安装使用、开发调试指南 |
| 架构 | [/llmdoc/architecture/](./architecture/) | 系统架构、模块设计 |
| 参考 | [/llmdoc/reference/](./reference/) | API 规范、数据模型 |

## 核心模块

```
minicc/
├── schemas.py   # 数据模型定义
├── config.py    # 配置管理
├── tools.py     # 工具函数实现
├── agent.py     # Agent 定义
├── app.py       # TUI 主应用
└── ui/          # UI 组件
```

## 技术栈

- **pydantic-ai**: Agent 框架，提供工具注册、流式输出
- **Textual**: TUI 框架，提供终端界面
- **Pydantic**: 数据验证和序列化
