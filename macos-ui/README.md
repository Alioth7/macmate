# MacMate macOS Native UI (Swift + Python)

This folder contains a native macOS frontend written in SwiftUI.
The backend remains Python and is accessed through JSON-over-stdin/stdout.

## Tech Stack

- Frontend: SwiftUI (macOS 13+)
- Runtime bridge: `Process` + JSON lines
- Backend: existing Python modules (`LLMBrain`, calendar adapter, memory manager)

## Files

- `../bridge_server.py`: Python bridge server
- `Package.swift`: Swift package manifest
- `Sources/MacMateUI/`: SwiftUI app source

## Run

1. Ensure Python dependencies are installed in your environment.
2. From repository root:

```bash
cd macos-ui
swift run
```

By default, frontend launches Python as `/usr/bin/python3` and bridge script as `../bridge_server.py`.

Optional env vars:

- `MACMATE_PYTHON`: python executable path
- `MACMATE_BRIDGE_PATH`: absolute path to `bridge_server.py`

Example:

```bash
MACMATE_PYTHON=/opt/homebrew/bin/python3 swift run
```

## Notes

- If chat says model unavailable, check your Python `config.py` and API key settings used by `core/llm_brain.py`.
- Calendar access still depends on macOS EventKit permission prompts.
