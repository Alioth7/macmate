# MacMate Codebase Functional Summary

This document provides a comprehensive functional summary of all key source code files in the **MacMate** project. The project is an AI-driven MacOS desktop assistant that integrates a Python-based ReAct agent with multiple frontends (Streamlit, CLI, and Native Swift MacOS UI).

## Root Directory

*   **`app.py`**: The Streamlit frontend entry point. Provides a web-based UI for interacting with the MacMate agent, viewing calendar events, checking the Eisenhower Matrix, managing long-term plans, and viewing daily summaries. Manages Streamlit session state and connects directly to the core Python logic.
*   **`bridge_server.py`**: The IPC (Inter-Process Communication) backend server. Handles requests from the native macOS UI (Swift) via standard input/output. It routes UI actions (like fetching calendar events, running shell commands, or chatting) to specific Python tools and manages the LLM cycles for non-UI (headless) interactions.
*   **`main.py`**: The Command Line Interface (CLI) entry point. Initializes the tools and starts the main interactive ReAct loop for terminal-based usage, enabling users to interact with the LLM and system tools directly from the terminal.

## Core Module (`core/`)

*   **`llm_brain.py`**: The core "brain" of MacMate. Implements the ReAct (Reasoning and Acting) agent logic. It constructs system prompts, manages the conversation history, calls tools via the Tool Registry, and handles the multi-step execution loop to fulfill user requests autonomosly.
*   **`tools.py`**: Implements the Tool Registry (`ToolRegistry`). It uses a decorator pattern to register ordinary Python functions as LLM-callable tools. It parses function signatures and docstrings to provide the LLM with structured information about how to use each tool.
*   **`llm_config.py`**: Manages configuration settings for Large Language Models (LLMs), including support for external APIs (like OpenAI compatible endpoints) and local deployment via Ollama. Allows toggling between modes.

## Tools Module (`tool/`)

*   **`calendar_adapter.py`**: Implements calendar management by interacting with macOS's native EventKit (often via AppleScript/JXA or native bridging). Provides tools to add, delete, read, and query calendar events, handling time-zone synchronization and validation.
*   **`memory_manager.py`**: Manages structured local storage (in JSON format) for "Long-term Plans" and "Daily Logs". Provides the LLM with read/write access to user's goals and historical summaries to ensure contextual continuity across sessions.
*   **`music_controller.py`**: Bridges the agent to macOS media players (Apple Music, Netease, etc.) using AppleScript integrations to play, pause, skip tracks, and adjust volume or fetch currently playing songs.
*   **`scene_profiles.py`**: Manages environment profiles such as "Focus" or "Relax". Can automatically toggle Do-Not-Disturb modes, close distracting apps, or open specific layouts using macOS automation frameworks.
*   **`shell_executor.py`**: Provides the LLM with the ability to execute terminal commands. Implements a critical **Three-Tier Security Model**:
    *   **Strict**: User must approve every command.
    *   **Agent**: Self-regulated by the agent, but blacklists dangerous commands (like `rm -rf`).
    *   **Self-Supervised**: Uses an LLM pass to review safety before executing.
*   **`system_monitor.py`**: Tracks system health (CPU, RAM) and monitors foreground application usage over time. Uses this data to generate productivity reports (focus vs. distraction hours) and triggers interventions or reminders.
*   **`weather_service.py`**: Provides current weather details and forecasts by querying external APIs or services, enabling the agent to factor weather into scheduling or user queries.
*   **`scheduler.py`**: Handles background cron-like scheduling for automated checking tasks or daily routines without active user prompts.

## Native MacOS UI (`macos-ui/`)

The native frontend is written in Swift (SwiftUI) and communicates with the Python agent via standard input/output (`bridge_server.py`).

*   **`Sources/MacMateUI/MacMateUIApp.swift`**: The main SwiftUI application lifecycle and entry point. It configures the window (e.g., hidden title bar) and launches the Python bridge process.
*   **`Sources/MacMateUI/RootView.swift`**: The main navigation structure (Sidebar and Detail views). Switches between different functional panels (Chat, Calendar, Productivity, etc.) and provides a global debug status overlay.
*   **`Sources/MacMateUI/PythonBridgeService.swift`**: The critical Swift-to-Python bridge logic. Spawns `bridge_server.py` as a subprocess, manages `stdin`/`stdout` pipes, and wraps JSON payload communication into async Swift functions. Tracks application state (chat history, calendar events, logs) fetched from Python.
*   **`Sources/MacMateUI/Panels.swift`**: Contains various core SwiftUI views:
    *   `ChatPanelView`: The main conversational interface, supporting streaming output and displaying the agent's internal reasoning trace (Step-by-Step execution).
    *   `CalendarPanelView`: Displays events in a Gantt-chart week view or list today view.
    *   `PlansPanelView` & `DailyPanelView`: UI for managing long-term plans with guiding prompts, and a daily log system with AI-assisted draft generation.
    *   `LLMSettingsPanelView`: Native configuration interface for setting up API keys, toggling Ollama local models, pulling new models, and configuring `ShellExecutor` security modes.
*   **`Sources/MacMateUI/NewPanels.swift`**: Contains additional domain-specific panels:
    *   `ScenePanelView`: Quick buttons to activate focus/relax modes.
    *   `MusicPanelView`: Controls media playback.
    *   `WeatherPanelView`: Native weather display.
*   **`Sources/MacMateUI/QuadrantPanelView.swift`**: Implements the Eisenhower Matrix UI using Swift Charts to plot tasks on Urgency/Importance axes.
*   **`Sources/MacMateUI/NativeCalendarService.swift`**: Swift-side native EventKit integration to directly fetch macOS calendar data without piping through Python, functioning as a fast data source for the UI.
*   **`Sources/MacMateUI/Models.swift`**: Defines data structures (e.g., `BridgeEnvelope`, `CalendarEvent`, `ProductivityUsageSummary`) and custom JSON parsing abstractions to safely parse data coming from Python.
*   **`Sources/MacMateUI/ChatInputField.swift`**: Custom text field handler for chat inputs.
