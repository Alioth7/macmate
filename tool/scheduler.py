"""
Lightweight scheduler for recurring and one-shot tasks.

Uses ``threading.Timer`` to avoid any external dependency. All tasks
survive only for the lifetime of the process – no persistent cron.
"""

import datetime
import json
import threading
import time
from typing import Callable, Dict, List, Optional

from core.tools import registry


class MacMateScheduler:
    """Schedule daily tasks (e.g. nightly briefing) and one-shot reminders."""

    def __init__(self):
        self._daily_tasks: List[Dict] = []
        self._reminders: List[Dict] = []
        self._timers: List[threading.Timer] = []
        self._stop_event = threading.Event()
        self._daily_thread: Optional[threading.Thread] = None
        self._reminder_callback: Optional[Callable] = None

        registry.bind_instance(self)

    # ------------------------------------------------------------------
    # Registered tools
    # ------------------------------------------------------------------
    @registry.register(
        "list_scheduled_tasks",
        "List all registered scheduled tasks and pending reminders. No args.",
    )
    def list_scheduled_tasks_tool(self) -> str:
        result = {
            "daily_tasks": self._daily_tasks,
            "reminders": [
                {
                    "time": r["time"],
                    "message": r["message"],
                    "fired": r.get("fired", False),
                }
                for r in self._reminders
            ],
        }
        return json.dumps(result, ensure_ascii=False, indent=2)

    @registry.register(
        "add_scheduled_reminder",
        "Add a one-shot reminder. Args: time(str 'HH:MM' today or 'YYYY-MM-DD HH:MM'), "
        "message(str reminder text).",
    )
    def add_scheduled_reminder_tool(self, time_str: str, message: str) -> str:
        time_str = (time_str or "").strip()
        message = (message or "").strip()
        if not time_str or not message:
            return "Error: time and message are required."

        target_dt = self._parse_time(time_str)
        if target_dt is None:
            return f"Error: cannot parse time '{time_str}'. Use 'HH:MM' or 'YYYY-MM-DD HH:MM'."

        now = datetime.datetime.now()
        delay = (target_dt - now).total_seconds()
        if delay < 0:
            return f"Error: time '{time_str}' is in the past."

        reminder = {
            "time": target_dt.strftime("%Y-%m-%d %H:%M"),
            "message": message,
            "fired": False,
        }
        self._reminders.append(reminder)

        def _fire():
            reminder["fired"] = True
            if self._reminder_callback:
                try:
                    self._reminder_callback(message)
                except Exception:
                    pass

        timer = threading.Timer(delay, _fire)
        timer.daemon = True
        timer.start()
        self._timers.append(timer)

        return (
            f"Success: reminder set for {reminder['time']}.\n"
            f"Message: {message}"
        )

    # ------------------------------------------------------------------
    # Daily task registration (called programmatically, not via LLM)
    # ------------------------------------------------------------------
    def register_daily_task(
        self,
        hour: int,
        minute: int,
        name: str,
        callback: Callable,
    ):
        """Register a task that runs every day at ``hour:minute``."""
        self._daily_tasks.append({
            "name": name,
            "time": f"{hour:02d}:{minute:02d}",
        })

        if self._daily_thread is None or not self._daily_thread.is_alive():
            self._start_daily_loop()

        # Store callback in list for the loop to execute.
        self._daily_tasks[-1]["_callback"] = callback

    def set_reminder_callback(self, callback: Callable):
        """Set the function called when a reminder fires."""
        self._reminder_callback = callback

    # ------------------------------------------------------------------
    # Internal daily loop
    # ------------------------------------------------------------------
    def _start_daily_loop(self):
        self._stop_event.clear()

        def _loop():
            while not self._stop_event.is_set():
                now = datetime.datetime.now()
                current_hm = now.strftime("%H:%M")
                for task in self._daily_tasks:
                    if task["time"] == current_hm:
                        cb = task.get("_callback")
                        if cb:
                            try:
                                cb()
                            except Exception:
                                pass
                # Sleep until the next minute boundary
                next_min = (now + datetime.timedelta(minutes=1)).replace(
                    second=0, microsecond=0
                )
                wait_sec = (next_min - datetime.datetime.now()).total_seconds()
                if wait_sec > 0:
                    self._stop_event.wait(wait_sec)

        self._daily_thread = threading.Thread(target=_loop, daemon=True)
        self._daily_thread.start()

    def stop(self):
        self._stop_event.set()
        for t in self._timers:
            t.cancel()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_time(raw: str) -> Optional[datetime.datetime]:
        raw = raw.strip()
        now = datetime.datetime.now()

        # Try full datetime
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.datetime.strptime(raw, fmt)
            except ValueError:
                continue

        # Try time-only (assume today)
        for fmt in ("%H:%M", "%H:%M:%S"):
            try:
                t = datetime.datetime.strptime(raw, fmt)
                return now.replace(
                    hour=t.hour, minute=t.minute, second=0, microsecond=0
                )
            except ValueError:
                continue

        return None
