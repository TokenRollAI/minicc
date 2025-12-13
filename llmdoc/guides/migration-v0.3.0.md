# v0.3.0 迁移指南（Breaking Change）

v0.3.0 对 MiniCC 做了大规模重构：对外仅保证 **TUI 行为**，原先的编程接口/模块路径不再保证兼容。

## 1. 新的目录结构

```
minicc/
├── cli.py        # CLI 入口（启动 TUI）
├── core/         # 运行时/模型/事件总线/MCP 预加载
├── tools/        # 工具实现（按职责拆分）
└── tui/          # Textual TUI
```

核心变化：
- **UI 事件通知重写**：TUI 直接消费 `agent.run_stream_events()` 的工具调用事件。
- **MCP 启动预加载**：启动阶段加载并缓存 toolsets，避免子代理重复加载。
- **子任务语义调整**：`task(wait=True)` 默认等待子代理完成并返回结果；支持 `wait_subagents()` 汇总等待。

## 2. 启动与调试

启动：

```bash
minicc
# 或
python -m minicc
```

Textual 开发模式：

```bash
uv run textual run --dev minicc.tui.app:MiniCCApp
```

显示完整 traceback：

```bash
export MINICC_DEBUG=1
minicc
```

## 3. MCP 严格模式（可选）

默认缺少 MCP 依赖/配置错误会告警并降级为“不加载 MCP”。如需严格失败：

```bash
export MINICC_MCP_STRICT=1
minicc
```

## 4. 常见行为变化

- **工具调用显示**：由 stream events 驱动，不再依赖 tools 内部回调。
- **自动滚动**：流式输出会实时更新，并在布局刷新后自动滚动到底部。
- **token 图标**：底边栏从 emoji 改为 `↑/↓`，避免部分终端显示方块。

