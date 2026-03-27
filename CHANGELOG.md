# MacMate Changelog

## 2026-03-27

### Bug Fixes

- **[Chat] Agent Chat Markdown 渲染**: 聊天气泡使用 `AttributedString(markdown:)` 渲染，支持 **粗体**、*斜体*、`代码`、[链接] 等 inline markdown 格式，同时保留换行。(`Panels.swift` bubble 函数)

- **[Chat] 输入框崩溃修复**: 将 `NSViewRepresentable` 自定义 `NSTextView` 回退为稳定的 `TextField` + `.onSubmit`，解决键入时反复触发 `Exception detected while handling key input` 的崩溃。(`ChatInputField.swift`)

- **[Chat] 聊天记录持久化**: 新增手动保存/加载聊天记录按钮，存储为 `cache/chat_history.json`。(`PythonBridgeService.swift`, `Panels.swift`)

- **[Daily] AI 日报生成失败**: `daily_ai_draft` handler 原来在日历不可用时直接返回 `{error: ...}`，前端不处理导致按钮无反应。修复：日历降级为可选，新增生产力数据，错误信息直接写入 summary 字段。(`bridge_server.py`)

- **[Daily] AI 日报移除 emoji**: prompt 和 system instruction 中明确禁止使用 emoji 输出。(`bridge_server.py`)

- **[Calendar] 日历工具对 Agent 不可见**: `calendar_adapter.py` 在文件顶部硬性 `import EventKit`，EventKit/PyObjC 不可用时整个模块 import 失败，导致 `@registry.register` 装饰器从未执行，日历相关工具（创建/删除/查询事件）在 Agent 的可用工具列表中完全缺失。修复：改为 soft-import，模块始终加载成功，工具始终注册。EventKit 不可用时工具调用返回明确错误信息。(`calendar_adapter.py`, `bridge_server.py`)

- **[Core] 未绑定工具调用崩溃**: 当工具注册成功但对应服务初始化失败时（如 EventKit 不可用），`ToolRegistry.get_tool()` 返回原始未绑定方法，调用时因缺少 `self` 参数而抛出 TypeError。修复：`get_tool()` 检测未绑定的实例方法，返回友好错误信息的包装函数。(`core/tools.py`)

- **[Calendar] 事件创建冲突检测**: `add_calendar_event` 工具内置冲突检测——创建前自动查询 EventKit 是否存在时间重叠的事件，有冲突则拒绝创建并返回冲突列表。新增 `add_calendar_event_confirmed` 工具用于用户确认后强制创建。(`calendar_adapter.py`, `llm_brain.py`)

- **[System] get_system_health 工具执行失败**: `collect_snapshot()` 的各子系统调用 (disk/memory/cpu/temperature/top_processes) 没有独立 try/except，任一子系统崩溃会导致整个工具返回异常。修复：每个子系统单独捕获异常，工具方法外层也加 try/except 保证永远返回有效 JSON。(`system_monitor.py`)

- **[Weather] 天气面板增强**: 从仅显示当前天气扩展为完整天气面板：逐时温度折线图 (Swift Charts)、降雨概率、3天预报卡片 (最高/低温、日出日落、UV)、城市切换、自动加载。(`weather_service.py`, `bridge_server.py`, `NewPanels.swift`)

### UI/UX Improvements

- **[全局] 中英文国际化**: 新增 `L10n.swift` 集中管理 ~70 个多语言键值对，侧边栏底部新增语言切换器 (中文/English)，所有面板文字跟随语言切换即时更新。(`L10n.swift`, `RootView.swift`, `Panels.swift`, `NewPanels.swift`, `QuadrantPanelView.swift`)

- **[全局] 移除装饰性 emoji**: 移除 🤖💡🎯🎵 等装饰性 emoji，保留 ✅ 等功能性符号。

- **[Sidebar] 图标对齐**: 侧边栏图标使用固定 20pt frame 对齐。(`RootView.swift`)

- **[LLM Settings] Shell 安全模式**: 新增 Shell Security Mode 选择器 (Strict/Agent/Self-supervised)，前端描述与后端实现对齐。(`Panels.swift`, `PythonBridgeService.swift`)

- **[Quadrant] 错误状态显示**: 四象限分析失败时显示错误信息和权限提示，而非静默失败。(`QuadrantPanelView.swift`)
