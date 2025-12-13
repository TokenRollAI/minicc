# 测试指南（v0.3.0）

本项目允许 breaking change，但要求核心行为（事件总线、ask_user、子代理等待、MCP 预加载、输入框交互）可被单元测试覆盖。

## 测试范围约定

当前默认测试**不覆盖**以下内容：

- 文件写入/编辑工具（`minicc/tools/file.py`）
- 文件搜索工具（`minicc/tools/search.py`）

原因：这些能力通常依赖本机文件系统状态与外部命令（ripgrep/agent-gear 索引），更适合在集成测试或手工验证中覆盖。

## 运行测试

在仓库根目录执行：

```bash
.venv/bin/pytest -q
```

如果你使用 uv 管理虚拟环境：

```bash
uv run pytest -q
```

## 现有用例覆盖点

- `tests/test_event_bus.py`：事件总线顺序与迭代
- `tests/test_ask_user_service.py`：ask_user 请求/取消语义
- `tests/test_subagent_service.py`：子代理前台/后台执行与事件
- `tests/test_wait_subagents_tool.py`：`task(wait=False)` + `wait_subagents()` 汇总等待
- `tests/test_mcp_preload.py`：MCP 预加载缓存与严格模式
- `tests/test_runtime_preload.py`：启动阶段预加载 toolsets 且子代理复用（不懒加载）
- `tests/test_chat_input.py`：输入框 Enter 提交、Ctrl+J 换行、@ 面板拦截键

