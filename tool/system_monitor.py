import datetime
import getpass
import json
import os
import pwd
import shutil
import subprocess
import threading
import time
from typing import Dict, List, Optional

from core.tools import registry

try:
    import psutil
except Exception:
    psutil = None


class SystemMonitor:
    """Collects local system telemetry and detects risky states."""

    def __init__(self, data_dir: str = "./data"):
        registry.bind_instance(self)
        self._prev_proc_cpu: Dict[int, float] = {}
        self._last_alert_at = 0.0
        self._alert_cooldown_sec = 45
        self._watch_thread: Optional[threading.Thread] = None
        self._watch_stop = threading.Event()

        self._data_dir = data_dir
        os.makedirs(self._data_dir, exist_ok=True)
        self._activity_file = os.path.join(self._data_dir, "activity_usage.json")
        self._usage_lock = threading.Lock()

        self._active_app: Optional[str] = None
        self._active_since_ts = time.time()

        self._activity_thread: Optional[threading.Thread] = None
        self._activity_stop = threading.Event()

        self._ensure_activity_store()

    @registry.register(
        "get_system_health",
        "Read current system health. Returns JSON string with CPU load, RAM usage, disk usage, temperature and top processes. No args.",
    )
    def get_system_health_tool(self) -> str:
        snapshot = self.collect_snapshot()
        return json.dumps(snapshot, ensure_ascii=False, indent=2)

    @registry.register(
        "check_system_risks",
        "Detect risky system state (memory pressure, disk full, process spike). Returns JSON alerts. No args.",
    )
    def check_system_risks_tool(self) -> str:
        snapshot = self.collect_snapshot()
        alerts = self._detect_alerts(snapshot)
        result = {
            "time": snapshot.get("time"),
            "alerts": alerts,
            "summary": "normal" if not alerts else f"{len(alerts)} risk(s) detected",
        }
        return json.dumps(result, ensure_ascii=False, indent=2)

    @registry.register(
        "sample_activity_usage",
        "Sample active app usage and background process load once. Returns JSON with current app and today's usage aggregate. No args.",
    )
    def sample_activity_usage_tool(self) -> str:
        record = self.sample_activity_once()
        summary = self.get_usage_summary(days=1)
        return json.dumps({"record": record, "summary": summary}, ensure_ascii=False, indent=2)

    @registry.register(
        "get_activity_usage_summary",
        "Get app usage summary from local tracker. Args: days(str optional, default='1'). Returns top apps and distraction ratio.",
    )
    def get_activity_usage_summary_tool(self, days: str = "1") -> str:
        days_int = self._safe_int(days, default=1, min_val=1, max_val=30)
        summary = self.get_usage_summary(days=days_int)
        return json.dumps(summary, ensure_ascii=False, indent=2)

    @registry.register(
        "analyze_schedule_reminders",
        "Analyze schedule reminders from calendar events and usage tracking. Args: schedule_events_json(str), focus_apps(str optional comma-separated), distraction_apps(str optional comma-separated).",
    )
    def analyze_schedule_reminders_tool(
        self,
        schedule_events_json: str,
        focus_apps: str = "Xcode,Cursor,Code,Terminal,iTerm2,PyCharm",
        distraction_apps: str = "WeChat,QQ,Douyin,Bilibili,YouTube,Steam,TikTok",
    ) -> str:
        try:
            events = json.loads(schedule_events_json) if schedule_events_json else []
            if not isinstance(events, list):
                events = []
        except Exception:
            events = []

        usage = self.get_usage_summary(days=1)
        reminders = self.analyze_schedule_reminders(
            events=events,
            usage_summary=usage,
            focus_apps=self._parse_app_list(focus_apps),
            distraction_apps=self._parse_app_list(distraction_apps),
        )
        return json.dumps({"usage": usage, "reminders": reminders}, ensure_ascii=False, indent=2)

    def collect_snapshot(self) -> Dict:
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        disk = self._disk_usage()
        memory = self._memory_usage()
        cpu = self._cpu_load()
        temperature = self._cpu_temperature()
        top_processes = self._top_processes(limit=8)

        return {
            "time": now,
            "disk": disk,
            "memory": memory,
            "cpu": cpu,
            "temperature": temperature,
            "top_processes": top_processes,
            "collector": "psutil" if psutil else "fallback",
        }

    def start_background_watch(self, on_alert, interval_sec: int = 12):
        if self._watch_thread and self._watch_thread.is_alive():
            return

        self._watch_stop.clear()

        def _watch_loop():
            while not self._watch_stop.is_set():
                try:
                    snapshot = self.collect_snapshot()
                    alerts = self._detect_alerts(snapshot)
                    if alerts and self._should_emit_alert():
                        on_alert(snapshot, alerts)
                        self._last_alert_at = time.time()
                except Exception:
                    pass

                self._watch_stop.wait(interval_sec)

        self._watch_thread = threading.Thread(target=_watch_loop, daemon=True)
        self._watch_thread.start()

    def stop_background_watch(self):
        self._watch_stop.set()

    def start_activity_watch(self, interval_sec: int = 30):
        if self._activity_thread and self._activity_thread.is_alive():
            return

        self._activity_stop.clear()

        def _activity_loop():
            while not self._activity_stop.is_set():
                try:
                    self.sample_activity_once(now_ts=time.time(), interval_sec=interval_sec)
                except Exception:
                    pass

                self._activity_stop.wait(interval_sec)

        self._activity_thread = threading.Thread(target=_activity_loop, daemon=True)
        self._activity_thread.start()

    def stop_activity_watch(self):
        self._activity_stop.set()

    def sample_activity_once(self, now_ts: Optional[float] = None, interval_sec: int = 30) -> Dict:
        if now_ts is None:
            now_ts = time.time()

        front_app = self._frontmost_app_name() or "Unknown"
        now_dt = datetime.datetime.fromtimestamp(now_ts)
        day_key = now_dt.strftime("%Y-%m-%d")

        with self._usage_lock:
            store = self._load_activity_store()
            day = self._ensure_day_node(store, day_key)

            prev_app = self._active_app or front_app
            elapsed = max(0.0, now_ts - self._active_since_ts)
            if elapsed > 0:
                day["apps"][prev_app] = round(float(day["apps"].get(prev_app, 0.0)) + elapsed, 2)

            if front_app != self._active_app:
                day["switches"].append(
                    {
                        "at": now_dt.strftime("%Y-%m-%d %H:%M:%S"),
                        "app": front_app,
                    }
                )
                day["switches"] = day["switches"][-300:]

            self._active_app = front_app
            self._active_since_ts = now_ts

            hotspots = self._estimate_background_hotspots(interval_sec=interval_sec)
            for row in hotspots:
                name = row["name"]
                day["background_hotspots"][name] = round(
                    float(day["background_hotspots"].get(name, 0.0)) + float(row["weighted_seconds"]),
                    2,
                )

            day["updated_at"] = now_dt.strftime("%Y-%m-%d %H:%M:%S")
            self._trim_days(store, keep_days=35)
            self._save_activity_store(store)

        return {
            "time": now_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "active_app": front_app,
            "estimated_interval_sec": interval_sec,
        }

    def get_usage_summary(self, days: int = 1, top_n: int = 8) -> Dict:
        days = max(1, min(days, 30))
        with self._usage_lock:
            store = self._load_activity_store()

        daily = store.get("daily", {})
        all_days = sorted(daily.keys())
        picked_days = all_days[-days:] if all_days else []

        app_seconds: Dict[str, float] = {}
        hotspot_seconds: Dict[str, float] = {}
        total_switches = 0

        for day_key in picked_days:
            node = daily.get(day_key, {})
            for app, seconds in (node.get("apps") or {}).items():
                app_seconds[app] = app_seconds.get(app, 0.0) + float(seconds)
            for proc_name, seconds in (node.get("background_hotspots") or {}).items():
                hotspot_seconds[proc_name] = hotspot_seconds.get(proc_name, 0.0) + float(seconds)
            total_switches += len(node.get("switches") or [])

        ranked_apps = sorted(app_seconds.items(), key=lambda x: x[1], reverse=True)
        ranked_hotspots = sorted(hotspot_seconds.items(), key=lambda x: x[1], reverse=True)

        distraction_keywords = self._parse_app_list(
            "WeChat,QQ,Douyin,Bilibili,YouTube,Steam,TikTok,Xiaohongshu"
        )
        focus_keywords = self._parse_app_list("Xcode,Cursor,Code,Terminal,iTerm2,PyCharm")

        distraction_seconds = self._sum_by_keywords(app_seconds, distraction_keywords)
        focus_seconds = self._sum_by_keywords(app_seconds, focus_keywords)
        total_seconds = sum(app_seconds.values())

        return {
            "days": days,
            "covered_dates": picked_days,
            "total_tracked_hours": round(total_seconds / 3600.0, 2),
            "focus_hours": round(focus_seconds / 3600.0, 2),
            "distraction_hours": round(distraction_seconds / 3600.0, 2),
            "distraction_ratio": round(distraction_seconds / total_seconds, 3) if total_seconds else 0.0,
            "context_switches": total_switches,
            "top_apps": [
                {"app": name, "hours": round(sec / 3600.0, 2)} for name, sec in ranked_apps[:top_n]
            ],
            "background_hotspots": [
                {"name": name, "weighted_hours": round(sec / 3600.0, 2)}
                for name, sec in ranked_hotspots[:top_n]
            ],
        }

    def analyze_schedule_reminders(
        self,
        events: List[Dict],
        usage_summary: Dict,
        focus_apps: Optional[List[str]] = None,
        distraction_apps: Optional[List[str]] = None,
    ) -> List[Dict]:
        focus_apps = focus_apps or self._parse_app_list("Xcode,Cursor,Code,Terminal,iTerm2,PyCharm")
        distraction_apps = distraction_apps or self._parse_app_list(
            "WeChat,QQ,Douyin,Bilibili,YouTube,Steam,TikTok"
        )

        reminders: List[Dict] = []
        now = datetime.datetime.now()

        top_apps = usage_summary.get("top_apps") or []
        app_hours_map = {str(item.get("app", "")): float(item.get("hours", 0.0)) for item in top_apps}

        focus_hours = sum(hours for app, hours in app_hours_map.items() if self._match_keywords(app, focus_apps))
        distraction_hours = sum(
            hours for app, hours in app_hours_map.items() if self._match_keywords(app, distraction_apps)
        )
        tracked_hours = float(usage_summary.get("total_tracked_hours", 0.0) or 0.0)
        distraction_ratio = float(usage_summary.get("distraction_ratio", 0.0) or 0.0)
        switches = int(usage_summary.get("context_switches", 0) or 0)

        if tracked_hours >= 2.0 and distraction_ratio >= 0.35:
            reminders.append(
                {
                    "type": "focus_recovery",
                    "severity": "medium",
                    "message": (
                        f"今天已跟踪 {tracked_hours:.1f}h，分心占比约 {distraction_ratio*100:.0f}% ，"
                        "建议开启 30 分钟专注时段并暂时关闭高干扰应用。"
                    ),
                    "action": "进入专注模式，保留 IDE/Terminal，暂停社交与视频应用。",
                }
            )

        if switches >= 40:
            reminders.append(
                {
                    "type": "context_switch_overload",
                    "severity": "medium",
                    "message": f"今日应用切换次数约 {switches} 次，任务上下文切换偏高。",
                    "action": "将相似任务批处理，设置 25-45 分钟单任务窗口。",
                }
            )

        upcoming = self._extract_upcoming_event(events, now)
        if upcoming:
            minutes_left = max(0, int((upcoming["start_dt"] - now).total_seconds() // 60))
            title = upcoming["title"]
            if distraction_ratio >= 0.3:
                reminders.append(
                    {
                        "type": "pre_event_focus",
                        "severity": "high",
                        "message": f"距离日程「{title}」还有 {minutes_left} 分钟，当前分心倾向偏高。",
                        "action": "立即切回准备应用（文档/IDE），先完成 1 个会前检查点。",
                    }
                )
            elif focus_hours <= distraction_hours and tracked_hours >= 1.5:
                reminders.append(
                    {
                        "type": "pre_event_warmup",
                        "severity": "low",
                        "message": f"距离日程「{title}」还有 {minutes_left} 分钟，建议进入预热阶段。",
                        "action": "打开相关材料并梳理 3 条待确认事项。",
                    }
                )

        hotspots = usage_summary.get("background_hotspots") or []
        if hotspots:
            top_hotspot = hotspots[0]
            if float(top_hotspot.get("weighted_hours", 0.0)) >= 1.0:
                reminders.append(
                    {
                        "type": "background_process_pressure",
                        "severity": "medium",
                        "message": (
                            f"后台进程 {top_hotspot.get('name')} 近期高负载累计约 "
                            f"{float(top_hotspot.get('weighted_hours', 0.0)):.1f}h。"
                        ),
                        "action": "检查是否为异常常驻进程，必要时在活动监视器中结束。",
                    }
                )

        if not reminders:
            reminders.append(
                {
                    "type": "status_ok",
                    "severity": "info",
                    "message": "当前使用行为与日程节奏基本一致。",
                    "action": "继续按既定计划执行，建议每 60-90 分钟做一次短休息。",
                }
            )

        return reminders

    def _should_emit_alert(self) -> bool:
        return time.time() - self._last_alert_at >= self._alert_cooldown_sec

    def _disk_usage(self) -> Dict:
        total, used, free = shutil.disk_usage("/")
        used_pct = round(used * 100.0 / total, 2) if total else 0.0
        return {
            "path": "/",
            "total_gb": round(total / (1024**3), 2),
            "used_gb": round(used / (1024**3), 2),
            "free_gb": round(free / (1024**3), 2),
            "used_percent": used_pct,
        }

    def _memory_usage(self) -> Dict:
        if psutil:
            vm = psutil.virtual_memory()
            return {
                "total_gb": round(vm.total / (1024**3), 2),
                "used_gb": round(vm.used / (1024**3), 2),
                "available_gb": round(vm.available / (1024**3), 2),
                "used_percent": round(vm.percent, 2),
            }

        # Fallback for macOS environments without psutil.
        try:
            total_bytes = self._read_int_cmd(["sysctl", "-n", "hw.memsize"])
            vm_out = subprocess.run(
                ["vm_stat"], capture_output=True, text=True, timeout=2.0, check=False
            ).stdout
            pagesize = self._parse_pagesize(vm_out)
            pages = self._parse_vm_pages(vm_out)

            free_pages = pages.get("Pages free", 0) + pages.get("Pages speculative", 0)
            inactive_pages = pages.get("Pages inactive", 0)
            available_bytes = (free_pages + inactive_pages) * pagesize
            used_bytes = max(0, total_bytes - available_bytes)
            used_pct = round(used_bytes * 100.0 / total_bytes, 2) if total_bytes else None

            return {
                "total_gb": round(total_bytes / (1024**3), 2),
                "used_gb": round(used_bytes / (1024**3), 2),
                "available_gb": round(available_bytes / (1024**3), 2),
                "used_percent": used_pct,
                "note": "collected via vm_stat/sysctl",
            }
        except Exception:
            return {
                "total_gb": None,
                "used_gb": None,
                "available_gb": None,
                "used_percent": None,
                "note": "memory detail unavailable",
            }

    def _cpu_load(self) -> Dict:
        load1, load5, load15 = os.getloadavg()
        logical_cores = os.cpu_count() or 1
        normalized_1m = round((load1 / logical_cores) * 100.0, 2)

        cpu_percent = None
        if psutil:
            cpu_percent = round(psutil.cpu_percent(interval=0.2), 2)

        return {
            "load_avg_1m": round(load1, 2),
            "load_avg_5m": round(load5, 2),
            "load_avg_15m": round(load15, 2),
            "logical_cores": logical_cores,
            "normalized_1m_percent": normalized_1m,
            "cpu_percent": cpu_percent,
        }

    def _cpu_temperature(self) -> Dict:
        # Preferred: psutil sensors if available.
        if psutil:
            try:
                sensors = psutil.sensors_temperatures()
                if sensors:
                    readings = []
                    for _, vals in sensors.items():
                        for item in vals:
                            if item.current is not None:
                                readings.append(float(item.current))
                    if readings:
                        return {
                            "celsius": round(sum(readings) / len(readings), 2),
                            "source": "psutil.sensors_temperatures",
                        }
            except Exception:
                pass

        # Fallback: thermal level on macOS (not exact temperature).
        try:
            out = subprocess.run(
                ["sysctl", "-n", "machdep.xcpm.cpu_thermal_level"],
                capture_output=True,
                text=True,
                timeout=1.5,
                check=False,
            )
            level = out.stdout.strip()
            if level:
                return {
                    "celsius": None,
                    "thermal_level": level,
                    "source": "sysctl.machdep.xcpm.cpu_thermal_level",
                }
        except Exception:
            pass

        return {
            "celsius": None,
            "source": "unavailable",
            "note": "CPU temperature sensor is unavailable in current environment",
        }

    def _top_processes(self, limit: int = 8) -> List[Dict]:
        if not psutil:
            return self._fallback_top_processes(limit)

        current_user = getpass.getuser()
        rows = []

        for proc in psutil.process_iter(["pid", "name", "username", "cpu_percent", "memory_percent", "status"]):
            try:
                info = proc.info
                pid = info.get("pid")
                cpu = float(info.get("cpu_percent") or 0.0)
                mem = float(info.get("memory_percent") or 0.0)
                prev = self._prev_proc_cpu.get(pid, cpu)
                spike = round(cpu - prev, 2)
                self._prev_proc_cpu[pid] = cpu

                rows.append(
                    {
                        "pid": pid,
                        "name": info.get("name") or "unknown",
                        "user": info.get("username") or "unknown",
                        "is_current_user": (info.get("username") == current_user),
                        "cpu_percent": round(cpu, 2),
                        "memory_percent": round(mem, 2),
                        "status": info.get("status") or "unknown",
                        "cpu_spike": spike,
                    }
                )
            except Exception:
                continue

        rows.sort(key=lambda x: (x["cpu_percent"], x["memory_percent"]), reverse=True)
        return rows[:limit]

    def _fallback_top_processes(self, limit: int = 8) -> List[Dict]:
        current_user = getpass.getuser()
        rows: List[Dict] = []
        try:
            out = subprocess.run(
                ["ps", "-arcxo", "pid,uid,pcpu,pmem,comm"],
                capture_output=True,
                text=True,
                timeout=2.0,
                check=False,
            ).stdout
            lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
            for line in lines[1 : limit + 20]:
                parts = line.split(None, 4)
                if len(parts) < 5:
                    continue
                pid = int(parts[0])
                uid = int(parts[1])
                cpu = float(parts[2])
                mem = float(parts[3])
                name = os.path.basename(parts[4])

                try:
                    user = pwd.getpwuid(uid).pw_name
                except Exception:
                    user = str(uid)

                prev = self._prev_proc_cpu.get(pid, cpu)
                spike = round(cpu - prev, 2)
                self._prev_proc_cpu[pid] = cpu

                rows.append(
                    {
                        "pid": pid,
                        "name": name,
                        "user": user,
                        "is_current_user": (user == current_user),
                        "cpu_percent": round(cpu, 2),
                        "memory_percent": round(mem, 2),
                        "status": "unknown",
                        "cpu_spike": spike,
                    }
                )
        except Exception:
            return []

        rows.sort(key=lambda x: (x["cpu_percent"], x["memory_percent"]), reverse=True)
        return rows[:limit]

    def _read_int_cmd(self, cmd: List[str]) -> int:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=1.5, check=False)
        return int((out.stdout or "0").strip())

    def _frontmost_app_name(self) -> Optional[str]:
        script = (
            'tell application "System Events"\n'
            'set frontApp to name of first application process whose frontmost is true\n'
            'return frontApp\n'
            "end tell"
        )
        try:
            out = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=1.2,
                check=False,
            )
            name = (out.stdout or "").strip()
            return name or None
        except Exception:
            return None

    def _estimate_background_hotspots(self, interval_sec: int = 30) -> List[Dict]:
        rows: List[Dict] = []
        for proc in self._top_processes(limit=10):
            cpu = float(proc.get("cpu_percent") or 0.0)
            is_current_user = bool(proc.get("is_current_user"))
            if is_current_user or cpu < 25:
                continue

            weight = min(1.0, cpu / 100.0)
            rows.append(
                {
                    "name": str(proc.get("name") or "unknown"),
                    "weighted_seconds": round(interval_sec * weight, 2),
                }
            )
        return rows

    def _ensure_activity_store(self):
        with self._usage_lock:
            if os.path.exists(self._activity_file):
                return
            init_data = {"daily": {}, "version": 1}
            with open(self._activity_file, "w", encoding="utf-8") as f:
                json.dump(init_data, f, ensure_ascii=False, indent=2)

    def _load_activity_store(self) -> Dict:
        if not os.path.exists(self._activity_file):
            return {"daily": {}, "version": 1}
        try:
            with open(self._activity_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return {"daily": {}, "version": 1}
            if "daily" not in data or not isinstance(data.get("daily"), dict):
                data["daily"] = {}
            return data
        except Exception:
            return {"daily": {}, "version": 1}

    def _save_activity_store(self, data: Dict):
        with open(self._activity_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _ensure_day_node(self, store: Dict, day_key: str) -> Dict:
        daily = store.setdefault("daily", {})
        node = daily.setdefault(day_key, {})
        node.setdefault("apps", {})
        node.setdefault("switches", [])
        node.setdefault("background_hotspots", {})
        node.setdefault("updated_at", "")
        return node

    def _trim_days(self, store: Dict, keep_days: int = 35):
        daily = store.get("daily", {})
        keys = sorted(daily.keys())
        if len(keys) <= keep_days:
            return
        for key in keys[: len(keys) - keep_days]:
            daily.pop(key, None)

    def _parse_app_list(self, raw: str) -> List[str]:
        items = [x.strip() for x in (raw or "").split(",")]
        return [x for x in items if x]

    def _sum_by_keywords(self, app_seconds: Dict[str, float], keywords: List[str]) -> float:
        total = 0.0
        for app, seconds in app_seconds.items():
            if self._match_keywords(app, keywords):
                total += float(seconds)
        return total

    def _match_keywords(self, app_name: str, keywords: List[str]) -> bool:
        app_lower = (app_name or "").lower()
        for kw in keywords:
            if kw.lower() in app_lower:
                return True
        return False

    def _extract_upcoming_event(self, events: List[Dict], now: datetime.datetime) -> Optional[Dict]:
        if not events:
            return None

        picked: List[Dict] = []
        for event in events:
            start_raw = str(event.get("Start") or event.get("start") or "")
            title = str(event.get("Task") or event.get("title") or "未命名事件")
            if not start_raw:
                continue

            start_dt = self._parse_datetime(start_raw)
            if not start_dt:
                continue

            delta_min = (start_dt - now).total_seconds() / 60.0
            if 0 <= delta_min <= 120:
                picked.append({"title": title, "start_dt": start_dt})

        if not picked:
            return None

        picked.sort(key=lambda x: x["start_dt"])
        return picked[0]

    def _parse_datetime(self, raw: str) -> Optional[datetime.datetime]:
        text = (raw or "").strip()
        if not text:
            return None
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.datetime.strptime(text, fmt)
            except Exception:
                continue
        return None

    def _safe_int(self, raw: str, default: int = 1, min_val: int = 1, max_val: int = 30) -> int:
        try:
            val = int(str(raw).strip())
            if val < min_val:
                return min_val
            if val > max_val:
                return max_val
            return val
        except Exception:
            return default

    def _parse_pagesize(self, vm_stat_output: str) -> int:
        # Example: "Mach Virtual Memory Statistics: (page size of 16384 bytes)"
        first = vm_stat_output.splitlines()[0] if vm_stat_output else ""
        for token in first.replace("(", " ").replace(")", " ").split():
            if token.isdigit():
                return int(token)
        return 4096

    def _parse_vm_pages(self, vm_stat_output: str) -> Dict[str, int]:
        pages: Dict[str, int] = {}
        for line in vm_stat_output.splitlines()[1:]:
            if ":" not in line:
                continue
            key, val = line.split(":", 1)
            num = "".join(ch for ch in val if ch.isdigit())
            if num:
                pages[key.strip()] = int(num)
        return pages

    def _detect_alerts(self, snapshot: Dict) -> List[Dict]:
        alerts: List[Dict] = []

        mem = snapshot.get("memory", {})
        mem_used_pct = mem.get("used_percent")
        mem_avail = mem.get("available_gb")
        if isinstance(mem_used_pct, (int, float)) and mem_used_pct >= 85:
            alerts.append(
                {
                    "type": "memory_pressure",
                    "severity": "high",
                    "message": f"RAM usage is high: {mem_used_pct}% (available: {mem_avail} GB)",
                    "action": "Open Activity Monitor and inspect Memory tab",
                }
            )

        disk = snapshot.get("disk", {})
        disk_used_pct = disk.get("used_percent")
        if isinstance(disk_used_pct, (int, float)) and disk_used_pct >= 90:
            alerts.append(
                {
                    "type": "disk_pressure",
                    "severity": "medium",
                    "message": f"Disk usage is high: {disk_used_pct}% on /",
                    "action": "Clean large files and caches",
                }
            )

        for proc in snapshot.get("top_processes", []):
            cpu = proc.get("cpu_percent", 0)
            spike = proc.get("cpu_spike", 0)
            is_current_user = proc.get("is_current_user", False)

            if cpu >= 80 and spike >= 35 and not is_current_user:
                alerts.append(
                    {
                        "type": "background_process_spike",
                        "severity": "high",
                        "message": (
                            f"Background process spike detected: {proc.get('name')} "
                            f"(pid={proc.get('pid')}, cpu={cpu}%, spike={spike}%)"
                        ),
                        "action": "Open Activity Monitor and verify this process",
                    }
                )

        return alerts
