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

    def __init__(self):
        registry.bind_instance(self)
        self._prev_proc_cpu: Dict[int, float] = {}
        self._last_alert_at = 0.0
        self._alert_cooldown_sec = 45
        self._watch_thread: Optional[threading.Thread] = None
        self._watch_stop = threading.Event()

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
