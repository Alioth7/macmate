"""
Music controller – Apple Music and NetEase Cloud Music (网易云音乐).

Apple Music supports full AppleScript control.
NetEase Music has no AppleScript dictionary, so we simulate media keys
through System Events.
"""

import json
import subprocess
from typing import Optional

from core.tools import registry


class MusicController:
    """Control music playback on macOS via AppleScript."""

    SUPPORTED_APPS = ("apple_music", "netease")

    def __init__(self):
        registry.bind_instance(self)

    # ------------------------------------------------------------------
    # Registered tools
    # ------------------------------------------------------------------
    @registry.register(
        "play_music",
        "Play music. Args: app(str 'apple_music'|'netease'), genre(str optional, "
        "playlist keyword – only works for Apple Music search).",
    )
    def play_music_tool(self, app: str = "apple_music", genre: str = "") -> str:
        app = self._normalise_app(app)
        if app == "apple_music":
            return self._apple_music_play(genre)
        elif app == "netease":
            return self._netease_play()
        return f"Error: unsupported app '{app}'."

    @registry.register(
        "pause_music",
        "Pause current music playback. Args: app(str 'apple_music'|'netease').",
    )
    def pause_music_tool(self, app: str = "apple_music") -> str:
        app = self._normalise_app(app)
        if app == "apple_music":
            return self._osascript('tell application "Music" to pause')
        elif app == "netease":
            return self._netease_toggle_play()
        return f"Error: unsupported app '{app}'."

    @registry.register(
        "next_track",
        "Skip to next track. Args: app(str 'apple_music'|'netease').",
    )
    def next_track_tool(self, app: str = "apple_music") -> str:
        app = self._normalise_app(app)
        if app == "apple_music":
            return self._osascript('tell application "Music" to next track')
        elif app == "netease":
            return self._netease_key("124")  # left=123, right=124
        return f"Error: unsupported app '{app}'."

    @registry.register(
        "previous_track",
        "Go to previous track. Args: app(str 'apple_music'|'netease').",
    )
    def previous_track_tool(self, app: str = "apple_music") -> str:
        app = self._normalise_app(app)
        if app == "apple_music":
            return self._osascript('tell application "Music" to previous track')
        elif app == "netease":
            return self._netease_key("123")
        return f"Error: unsupported app '{app}'."

    @registry.register(
        "get_now_playing",
        "Get info about the currently playing track. No args. "
        "Returns track name, artist, album (Apple Music only; "
        "NetEase returns limited info).",
    )
    def get_now_playing_tool(self) -> str:
        # Try Apple Music first
        script = (
            'try\n'
            '  tell application "Music"\n'
            '    if player state is playing then\n'
            '      set t to name of current track\n'
            '      set a to artist of current track\n'
            '      set al to album of current track\n'
            '      return "Apple Music | " & t & " - " & a & " [" & al & "]"\n'
            '    else\n'
            '      return "Apple Music is not playing."\n'
            '    end if\n'
            '  end tell\n'
            'on error\n'
            '  return "Apple Music not running."\n'
            'end try'
        )
        result = self._osascript(script)

        # Check if NeteaseMusic is running
        netease_check = self._osascript(
            'tell application "System Events" to '
            '(name of processes) contains "NeteaseMusic"'
        )
        netease_status = ""
        if "true" in netease_check.lower():
            netease_status = " | 网易云音乐运行中（无法获取曲目详情）"

        return result + netease_status

    @registry.register(
        "set_volume",
        "Set system output volume. Args: level(str 0-100).",
    )
    def set_volume_tool(self, level: str = "50") -> str:
        try:
            vol = max(0, min(100, int(level)))
        except (ValueError, TypeError):
            return "Error: volume must be a number 0-100."
        # macOS volume scale is 0-100
        script = f'set volume output volume {vol}'
        return self._osascript(script) or f"Volume set to {vol}"

    # ------------------------------------------------------------------
    # Apple Music helpers
    # ------------------------------------------------------------------
    def _apple_music_play(self, genre: str = "") -> str:
        if not genre:
            # Just hit play
            return self._osascript('tell application "Music" to play')

        # Search for a playlist matching the genre keyword
        script = (
            f'tell application "Music"\n'
            f'  set matchedPlaylists to (every playlist whose name contains "{genre}")\n'
            f'  if (count of matchedPlaylists) > 0 then\n'
            f'    play item 1 of matchedPlaylists\n'
            f'    return "Playing playlist matching: {genre}"\n'
            f'  else\n'
            f'    play\n'
            f'    return "No playlist matching \'{genre}\' found, playing current queue."\n'
            f'  end if\n'
            f'end tell'
        )
        return self._osascript(script)

    # ------------------------------------------------------------------
    # NetEase Music helpers (simulated keypresses)
    # ------------------------------------------------------------------
    def _netease_play(self) -> str:
        """Activate NetEase Music and press space to play."""
        self._osascript('tell application "NeteaseMusic" to activate')
        return self._netease_toggle_play()

    def _netease_toggle_play(self) -> str:
        """Simulate spacebar in NetEase Music for play/pause toggle."""
        script = (
            'tell application "System Events"\n'
            '  tell process "NeteaseMusic"\n'
            '    set frontmost to true\n'
            '  end tell\n'
            '  key code 49\n'  # spacebar
            'end tell'
        )
        return self._osascript(script) or "NetEase Music: toggled play/pause"

    def _netease_key(self, key_code: str) -> str:
        """Send a specific key code to NetEase Music."""
        script = (
            'tell application "System Events"\n'
            '  tell process "NeteaseMusic"\n'
            '    set frontmost to true\n'
            '  end tell\n'
            f'  key code {key_code}\n'
            'end tell'
        )
        return self._osascript(script) or "ok"

    # ------------------------------------------------------------------
    # Common
    # ------------------------------------------------------------------
    @staticmethod
    def _osascript(script: str) -> str:
        try:
            r = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, text=True, timeout=5, check=False,
            )
            return (r.stdout or "").strip() or (r.stderr or "").strip() or "ok"
        except subprocess.TimeoutExpired:
            return "timeout"
        except Exception as exc:
            return f"error: {exc}"

    @staticmethod
    def _normalise_app(app: str) -> str:
        app = (app or "").strip().lower().replace(" ", "_")
        aliases = {
            "apple": "apple_music",
            "music": "apple_music",
            "applemusic": "apple_music",
            "netease": "netease",
            "neteasemusic": "netease",
            "网易云": "netease",
            "网易云音乐": "netease",
        }
        return aliases.get(app, app)
