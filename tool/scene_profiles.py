"""
Scene profile automation – focus / relax modes and app management.

All macOS interactions go through ``osascript`` (AppleScript) or the
``open`` / ``shortcuts`` CLI to avoid extra dependencies.
"""

import json
import subprocess
from typing import List

from core.tools import registry


class SceneProfileManager:
    """Predefined scene profiles that orchestrate multiple macOS apps/settings."""

    # Defaults – users can customise via long-term plans or chat.
    FOCUS_CLOSE_APPS = ["WeChat", "QQ", "Telegram", "Discord", "Messages"]
    FOCUS_OPEN_APPS = ["Terminal"]
    RELAX_CLOSE_APPS = ["Xcode", "Cursor", "Code", "Terminal", "iTerm2", "PyCharm"]
    RELAX_OPEN_APPS: List[str] = []  # user-dependent

    def __init__(self):
        registry.bind_instance(self)

    # ------------------------------------------------------------------
    # Registered tools
    # ------------------------------------------------------------------
    @registry.register(
        "activate_focus_mode",
        "Activate Focus/Development mode: enable DND, close social apps, "
        "open IDE/Terminal. No args.",
    )
    def activate_focus_mode_tool(self) -> str:
        results: List[str] = []

        # 1. Enable Do-Not-Disturb
        dnd = self._set_dnd(True)
        results.append(f"勿扰模式: {dnd}")

        # 2. Close social apps
        for app in self.FOCUS_CLOSE_APPS:
            r = self._quit_app(app)
            if "quit" in r.lower() or "not running" in r.lower():
                results.append(f"关闭 {app}: OK")

        # 3. Open dev apps
        for app in self.FOCUS_OPEN_APPS:
            self._open_app(app)
            results.append(f"启动 {app}")

        return "✅ 已进入专注开发模式\n" + "\n".join(results)

    @registry.register(
        "activate_relax_mode",
        "Activate Relax/Off-work mode: close office apps, disable DND. No args.",
    )
    def activate_relax_mode_tool(self) -> str:
        results: List[str] = []

        # 1. Close work apps
        for app in self.RELAX_CLOSE_APPS:
            r = self._quit_app(app)
            if "quit" in r.lower() or "not running" in r.lower():
                results.append(f"关闭 {app}: OK")

        # 2. Disable DND
        dnd = self._set_dnd(False)
        results.append(f"勿扰模式: {dnd}")

        # 3. Open relax apps
        for app in self.RELAX_OPEN_APPS:
            self._open_app(app)
            results.append(f"启动 {app}")

        return "🎉 已进入休闲模式\n" + "\n".join(results)

    @registry.register(
        "toggle_dnd",
        "Toggle macOS Do-Not-Disturb. Args: enabled(str 'true'|'false').",
    )
    def toggle_dnd_tool(self, enabled: str = "true") -> str:
        on = enabled.strip().lower() in ("true", "1", "yes", "on")
        return self._set_dnd(on)

    @registry.register(
        "close_apps",
        "Quit one or more macOS applications. Args: app_names(str comma-separated).",
    )
    def close_apps_tool(self, app_names: str) -> str:
        names = [n.strip() for n in (app_names or "").split(",") if n.strip()]
        if not names:
            return "Error: no app names provided."
        results = []
        for name in names:
            results.append(f"{name}: {self._quit_app(name)}")
        return "\n".join(results)

    @registry.register(
        "open_apps",
        "Launch one or more macOS applications. Args: app_names(str comma-separated).",
    )
    def open_apps_tool(self, app_names: str) -> str:
        names = [n.strip() for n in (app_names or "").split(",") if n.strip()]
        if not names:
            return "Error: no app names provided."
        results = []
        for name in names:
            results.append(f"{name}: {self._open_app(name)}")
        return "\n".join(results)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _run_osascript(script: str) -> str:
        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            out = (result.stdout or "").strip()
            err = (result.stderr or "").strip()
            return out or err or "ok"
        except subprocess.TimeoutExpired:
            return "timeout"
        except Exception as exc:
            return f"error: {exc}"

    @staticmethod
    def _open_app(name: str) -> str:
        try:
            subprocess.run(
                ["open", "-a", name],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            return "launched"
        except Exception as exc:
            return f"error: {exc}"

    def _quit_app(self, name: str) -> str:
        script = (
            f'if application "{name}" is running then\n'
            f'  tell application "{name}" to quit\n'
            f'  return "quit"\n'
            f"else\n"
            f'  return "not running"\n'
            f"end if"
        )
        return self._run_osascript(script)

    def _set_dnd(self, on: bool) -> str:
        """Toggle macOS Focus / Do-Not-Disturb.

        Strategy (ordered by reliability on macOS Ventura/Sonoma/Sequoia):
          1. GUI scripting: click the Focus button in Control Center
          2. Shortcuts CLI: user-created "Focus On"/"Focus Off" shortcuts
          3. Fallback: report manual instruction
        """
        # --- Method 1: GUI scripting via Control Center ---
        # Click the Focus menu bar item to toggle. We detect current state
        # by checking the AXValue or just toggle it.
        toggle_script = '''
tell application "System Events"
    tell process "ControlCenter"
        -- Find the Focus menu bar extra
        set focusItem to missing value
        repeat with mi in menu bar items of menu bar 1
            try
                if description of mi contains "专注模式" or description of mi contains "Focus" then
                    set focusItem to mi
                    exit repeat
                end if
            end try
        end repeat

        if focusItem is not missing value then
            click focusItem
            delay 0.5
            -- Look for the "专注模式" / "Focus" toggle or "勿扰模式" / "Do Not Disturb"
            try
                tell window 1
                    click (first checkbox whose description contains "勿扰" or description contains "Do Not Disturb")
                end tell
            on error
                -- If the toggle panel is already showing, just close it
                try
                    key code 53 -- Escape to close
                end try
            end try
            return "toggled"
        else
            return "focus_item_not_found"
        end if
    end tell
end tell
'''
        result = self._run_osascript(toggle_script)

        if "toggled" in result:
            return "enabled" if on else "disabled"

        # --- Method 2: Shortcuts CLI ---
        shortcut_name = "Focus On" if on else "Focus Off"
        try:
            r = subprocess.run(
                ["shortcuts", "run", shortcut_name],
                capture_output=True, text=True, timeout=5, check=False,
            )
            if r.returncode == 0:
                state = "enabled" if on else "disabled"
                return f"{state} (via Shortcuts)"
        except Exception:
            pass

        # --- Fallback ---
        action = "开启" if on else "关闭"
        return (
            f"⚠️ 自动切换勿扰模式失败。请手动{action}：\n"
            f"点击菜单栏右上角「控制中心」→「专注模式」→「勿扰模式」\n"
            f"(或创建名为 '{shortcut_name}' 的快捷指令以实现自动化)"
        )
