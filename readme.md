[English](#english) | [中文](#中文)

---

<a name="english"></a>
# MacMate - Your AI-Driven macOS Assistant

**This project is still under development and many functions have not been fully verified.**

--- 

### Usage:
```bash
cd macos-ui/
swift run
```

---

MacMate is an intelligent, privacy-first desktop assistant designed specifically for macOS. By deeply integrating the ReAct (Reasoning and Acting) agent framework with native macOS capabilities, MacMate transcends standard chat interfaces, functioning as an active, localized copilot that understands your system, habits, and schedule.

## ✨ Core Features & Innovations

### 🧠 Autonomous ReAct Agent Core
At the heart of MacMate is a sophisticated LLM-driven "Brain" (`core/llm_brain.py`) that autonomously orchestrates complex, multi-step tasks. By continually assessing your context, managing conversation history, and invoking a flexible Tool Registry, the agent understands your goals and executes them intelligently, without requiring rigid, step-by-step commands.

### 🛡️ Three-Tier Security Shell Execution
Security is paramount when an AI manipulates your operating system. MacMate introduces an innovative three-tier command execution sandbox:
- **Strict Mode**: Ultimate user control with explicit manual approval required for every shell command.
- **Agent Mode**: Intelligent autonomy governed by a rigorous hardcoded blacklist, preventing destructive actions (e.g., `rm -rf`, `mkfs`).
- **Self-Supervised Mode**: Next-generation safety that uses the LLM as an AI-auditor to dynamically evaluate and validate the safety of requested commands before execution.

### 📅 Intelligent Time & Task Matrix
Beyond creating simple calendar events, MacMate engages in deep temporal reasoning:
- Native integration with **Apple EventKit** ensures seamless synchronization with your iCloud/local calendars.
- An AI-powered **Eisenhower Matrix (Quadrant Analysis)** visually plots your schedule on Urgency and Importance axes using Swift Charts, transforming raw calendar data into actionable, prioritized workloads.

### 🧘 Contextual Scene Automation
MacMate enhances your workflow through instant **Scene Profiles**. With a single command, the agent can pivot your entire macOS environment—toggling Do-Not-Disturb modes, launching or hiding specific applications, and controlling your media players (Apple Music/Netease)—instantly setting the stage for "Deep Work" or "Relaxation".

### 📊 Automated Productivity Monitoring
Operating quietly in the background, MacMate monitors system health and foreground app usage. It automatically calculates your "focus vs. distraction" ratio to generate highly personalized daily logs and intelligent productivity reminders. It tracks your workflow without the friction of manual time-logging.

### 💻 Elegant Dual-Architecture Interface
- **Native SwiftUI Mac App**: A beautifully designed, frictionless Swift interface (`macos-ui`) that feels right at home on macOS. Enjoy rich visualizations like Gantt charts and scatter plots, running with low latency via robust JSON-over-stdout IPC (`PythonBridgeService`).
- **Versatile Fallbacks**: Also includes a terminal Command Line Interface (CLI) and a Streamlit web interface, catering seamlessly to developers, power users, and tinkerers.

### 🔒 Uncompromising Privacy (Ollama Native)
MacMate stores all memory—your daily logs, long-term plans, and configurations—locally on your disk. For the truly privacy-conscious, MacMate features **first-class Ollama integration**. You can download and run advanced LLMs (like Qwen2.5) locally directly from the UI, ensuring your sensitive desktop data never leaves your machine.

---

<a name="中文"></a>
# MacMate - 你的 AI 驱动 macOS 桌面专属助理

**这个项目仍在开发，很多功能尚未经过完善的测试。**  

MacMate 是一款专为 macOS 设计的智能、注重隐私的桌面助理。通过深度整合 ReAct (Reasoning and Acting) 代理框架与 macOS 原生功能，MacMate 超越了标准的聊天界面，成为一个能够理解你的系统、习惯和日程的活跃、本地化的 copilot (副驾驶)。

## ✨ 核心特性与创新

### 🧠 自主 ReAct Agent 核心
MacMate 的核心是一个复杂的 LLM 驱动的“大脑” (`core/llm_brain.py`)，它能够自主编排复杂的多步任务。通过持续评估你的上下文、管理对话历史以及调用灵活的工具注册表 (Tool Registry)，Agent 能够理解你的目标并智能地执行，而无需你死板地下达精确指令。

### 🛡️ 三级安全 Shell 执行
当 AI 能够操作你的操作系统时，安全性至关重要。MacMate 引入了创新的三级命令执行沙盒：
- **Strict (严格模式)**：绝对的用户控制权，每一个 Shell 命令在执行前都必须经过你的手动确认。
- **Agent (代理模式)**：智能自主模式，受严格的硬编码黑名单控制，拦截破坏性行为 (如 `rm -rf`, `mkfs`)。
- **Self-Supervised (自我监督模式)**：下一代安全机制，利用 LLM 本身作为 AI 审计员，在执行请求的命令前动态评估并验证其安全性。

### 📅 智能时间与任务矩阵
MacMate 不仅仅是帮你创建简单的日历事件，它具备深度的事件推理能力：
- 通过原生集成 **Apple EventKit**，确保与你的 iCloud 或本地日历实现极速无缝的同步。
- AI 驱动的**艾森豪威尔矩阵 (第一性原理/象限分析)** 能够使用 Swift Charts 在“紧急”和“重要”两个维度上以可视化方式绘制你的日程安排，将原始日历数据转化为可执行的优先级工作负载。

### 🧘 上下文场景自动化 (Scene Profiles)
MacMate 可以瞬间切换你的工作流。只需一句指令，Agent 就可以改变你的整个 macOS 环境状态——自如地切换勿扰模式 (DND)、启动或隐藏特定应用程序、控制你的媒体播放器 (Apple Music/网易云音乐)——瞬间为你搭建好“深度工作”或“放松休闲”的理想舞台。

### 📊 自动化生产力监控
MacMate 会在后台安静地运行，监控系统健康状态和前台应用的使用情况。它能自动计算你的“专注”与“分心”时长比例，生成高度个性化的日常日志 (Daily Logs) 及智能生产力提醒。它可以追踪你的工作流，完全免除手动记录时间的繁琐。

### 💻 优雅的双架构用户界面
- **原生 SwiftUI Mac 应用**：精心设计的原生 Swift 界面 (`macos-ui`) ，完美契合 macOS 审美。通过健壮的 JSON-over-stdout 进程间通信 (`PythonBridgeService`) 实现低延迟交互，支持甘特图 (Gantt charts) 和散点图等丰富的可视化图表。
- **丰富的备选方案**：同时提供命令行界面 (CLI) 和 Streamlit Web 界面，无缝满足开发者、高级用户和喜欢折腾的极客的需求。

### 🔒 绝不妥协的隐私保护 (原生支持 Ollama)
MacMate 所有的记忆数据——你的日常日志、长期规划以及配置信息——都百分之百本地存储在你的硬盘上。对于极致隐私的拥趸，MacMate 提供了 **一流的 Ollama 集成支持**。你可以直接从 UI 界面下载并运行高级的本地 LLM 模型 (如 Qwen2.5 / DeepSeek 等) 完全离线使用，确保你的任何桌面敏感数据永远不会离开你的电脑。
