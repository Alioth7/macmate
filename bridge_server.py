import json
import shutil
import subprocess
import sys
import traceback
from datetime import datetime, timedelta

import requests

from tool.memory_manager import MemoryManager
from tool.system_monitor import SystemMonitor
from tool.shell_executor import ShellExecutor
from tool.scene_profiles import SceneProfileManager
from tool.music_controller import MusicController
from tool.weather_service import WeatherService
from tool.scheduler import MacMateScheduler
from core.llm_config import LLMConfigStore

try:
    from core.llm_brain import LLMBrain
except Exception:
    LLMBrain = None

try:
    from tool.calendar_adapter import MacCalendarAdapter
except Exception:
    MacCalendarAdapter = None


class BridgeRuntime:
    def __init__(self):
        self.adapter = None
        self.calendar_error = None

        if MacCalendarAdapter is not None:
            try:
                self.adapter = MacCalendarAdapter()
            except Exception as exc:
                self.calendar_error = str(exc)
        else:
            self.calendar_error = "Calendar adapter unavailable. EventKit/PyObjC may not be installed."

        self.memory = MemoryManager("./data")
        self.monitor = SystemMonitor()
        self.monitor.start_activity_watch(interval_sec=30)
        self.shell_executor = ShellExecutor(mode="agent")
        self.scene_profiles = SceneProfileManager()
        self.music_controller = MusicController()
        self.weather_service = WeatherService()
        self.scheduler = MacMateScheduler()
        self.llm_config_store = LLMConfigStore("./data/llm_config.json")
        self.brain = None

        if LLMBrain is not None:
            try:
                self.brain = LLMBrain()
                # Register nightly briefing task
                def _nightly():
                    if self.brain:
                        try:
                            self.brain.run_cycle("请根据今天的使用数据和日程，生成一份每日简报并保存。")
                        except Exception:
                            pass
                self.scheduler.register_daily_task(22, 0, "每日简报", _nightly)
            except Exception:
                self.brain = None

    def handle(self, action, payload):
        payload = payload or {}

        def _ollama_host():
            cfg = self.llm_config_store.load()
            return (cfg.get("ollama_host") or "http://127.0.0.1:11434").rstrip("/")

        def _ollama_tags(host: str, timeout_sec: float = 1.5):
            url = host + "/api/tags"
            response = requests.get(url, timeout=timeout_sec)
            response.raise_for_status()
            return response.json()

        if action == "health":
            return {
                "status": "ok",
                "chat_available": self.brain is not None,
                "calendar_available": self.adapter is not None,
                "calendar_error": self.calendar_error,
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

        if action == "chat":
            if self.brain is None:
                return {
                    "error": "LLM backend unavailable. Please configure LLM in Settings.",
                    "answer": "目前聊天模型不可用，请先在设置里配置 LLM（API 或 Ollama）。",
                }

            prompt = (payload.get("prompt") or "").strip()
            if not prompt:
                return {"error": "prompt is required", "answer": "请输入内容。"}

            steps = []

            def cb(step_type, content):
                steps.append({"type": step_type, "content": str(content)})
                stream_event = {
                    "id": None,
                    "ok": True,
                    "result": {
                        "event": "trace",
                        "type": step_type,
                        "content": str(content)
                    }
                }
                sys.stdout.write(json.dumps(stream_event, ensure_ascii=False) + "\n")
                sys.stdout.flush()

            answer = self.brain.run_cycle(prompt, step_callback=cb)
            return {"answer": answer, "steps": steps}

        if action == "chat_clear":
            if self.brain:
                self.brain.clear_history()
            return {"status": "ok"}

        if action == "calendar_detailed":
            if self.adapter is None:
                return {"error": self.calendar_error or "Calendar backend unavailable.", "events": []}

            start = payload.get("start_time")
            end = payload.get("end_time")

            if not start or not end:
                now = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                start = now.strftime("%Y-%m-%d %H:%M")
                end = (now + timedelta(days=14)).strftime("%Y-%m-%d %H:%M")

            events = self.adapter.get_detailed_events(start, end)
            return {"events": events, "start_time": start, "end_time": end}

        if action == "update_event_time":
            if self.adapter is None:
                return {"result": self.calendar_error or "Calendar backend unavailable."}

            result = self.adapter.update_event_time(
                title=payload.get("title", ""),
                old_start_str=payload.get("old_start", ""),
                new_start_str=payload.get("new_start", ""),
                new_end_str=payload.get("new_end", ""),
            )
            return {"result": result}

        if action == "plans_list":
            return {"plans": self.memory.get_plans_data()}

        if action == "plan_add":
            result = self.memory.add_plan(
                content=payload.get("content", ""),
                custom_prompt=payload.get("custom_prompt", ""),
                target_date=payload.get("target_date", ""),
            )
            return {"result": result}
            
        if action == "plan_update":
            result = self.memory.update_plan(
                id=payload.get("id"),
                content=payload.get("content", ""),
                custom_prompt=payload.get("custom_prompt", ""),
                target_date=payload.get("target_date", ""),
            )
            return {"result": result}
            
        if action == "plan_delete":
            result = self.memory.delete_plan(
                id=payload.get("id"),
            )
            return {"result": result}

        if action == "daily_logs":
            return {"logs": self.memory.get_logs_data()}

        if action == "daily_ai_draft":
            if self.brain is None or self.adapter is None:
                return {"error": "LLM or Calendar unavailable."}
            
            now = datetime.now()
            start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0).strftime("%Y-%m-%d %H:%M")
            end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=0).strftime("%Y-%m-%d %H:%M")
            events = self.adapter.get_detailed_events(start_of_day, end_of_day)
            event_text = json.dumps(events, ensure_ascii=False) if events else "今天没有日历事件。"
            
            plans_context = ""
            raw_plans = self.memory.get_plans_data()
            for p in raw_plans:
                if p.get("status") == "active":
                    plans_context += f"- 目标: {p['content']}\n"
                    if p.get("custom_prompt"):
                        plans_context += f"  > 上下文/指导原则: {p['custom_prompt']}\n"
                        
            prompt = f"""请根据今天的日程和我的长期目标，为我生成一份每日总结和改进建议。
【长期目标与指导原则】
{plans_context}
【今日日程】
{event_text}
【要求】
1. 总结今日完成情况，计算时间利用率（如果数据允许）。
2. 结合我的长期目标（特别是指导原则）进行点评。
3. 使用分隔符 "### 改进建议" 将总结和建议分开。"""
            try:
                response = self.brain.generate_text(prompt, system_instruction="你是一个高效的个人成长助手。请客观、犀利地分析日报。")
                if "### 改进建议" in response:
                    parts = response.split("### 改进建议")
                    summary = parts[0].strip()
                    suggestion = parts[1].strip()
                else:
                    summary = response
                    suggestion = "请根据总结自行补充。"
                return {"summary": summary, "suggestion": suggestion}
            except Exception as e:
                return {"error": str(e)}

        if action == "quadrant_analysis":
            if self.brain is None or self.adapter is None:
                return {"error": "LLM backend or Calendar unavailable.", "data": []}

            period = payload.get("period", "today")
            now = datetime.now()
            now_str = now.strftime("%Y-%m-%d %H:%M")
            if period == "today":
                tomorrow = now + timedelta(days=1)
                end_dt = tomorrow.replace(hour=6, minute=0, second=0, microsecond=0)
                end_str = end_dt.strftime("%Y-%m-%d %H:%M")
            else:
                end_str = (now + timedelta(days=7)).strftime("%Y-%m-%d %H:%M")
                
            events_data = self.adapter.get_detailed_events(now_str, end_str)
            events_text = json.dumps(events_data, ensure_ascii=False) if events_data else "没有事件"
            
            try:
                classified = self.brain.classify_events(events_text)
                return {"data": classified or []}
            except Exception as e:
                return {"error": str(e), "data": []}

        if action == "daily_save":
            date_str = payload.get("date") or datetime.now().strftime("%Y-%m-%d")
            result = self.memory.save_daily_log(
                date=date_str,
                summary=payload.get("summary", ""),
                suggestions=payload.get("suggestions", ""),
            )
            return {"result": result}

        if action == "system_health":
            try:
                health = self.monitor.collect_snapshot()
                return {"health": health}
            except Exception as exc:
                return {"error": f"system health collection failed: {exc}"}

        if action == "system_risks":
            try:
                snapshot = self.monitor.collect_snapshot()
                alerts = self.monitor._detect_alerts(snapshot)
                return {"time": snapshot.get("time"), "alerts": alerts, "snapshot": snapshot}
            except Exception as exc:
                return {"error": f"system risk detection failed: {exc}"}

        if action == "productivity_reminders":
            try:
                self.monitor.sample_activity_once()
                usage = self.monitor.get_usage_summary(days=1)

                now = datetime.now()
                start = now.replace(hour=0, minute=0, second=0, microsecond=0).strftime("%Y-%m-%d %H:%M")
                end = now.replace(hour=23, minute=59, second=59, microsecond=0).strftime("%Y-%m-%d %H:%M")

                events = []
                if self.adapter is not None:
                    events = self.adapter.get_detailed_events(start, end)

                reminders = self.monitor.analyze_schedule_reminders(events=events or [], usage_summary=usage)
                return {
                    "time": now.strftime("%Y-%m-%d %H:%M:%S"),
                    "usage": usage,
                    "events": events or [],
                    "reminders": reminders,
                }
            except Exception as exc:
                return {"error": f"productivity reminder analysis failed: {exc}"}

        if action == "shell_exec":
            cmd = payload.get("command", "")
            return {"result": self.shell_executor.run_shell_command_tool(command=cmd)}

        if action == "shell_security_mode":
            mode = payload.get("mode")
            if mode:
                return {"result": self.shell_executor.set_shell_security_mode_tool(mode=mode)}
            return {"result": self.shell_executor.get_shell_security_mode_tool()}

        if action == "scene_activate":
            profile = payload.get("profile", "focus")
            if profile == "relax":
                return {"result": self.scene_profiles.activate_relax_mode_tool()}
            return {"result": self.scene_profiles.activate_focus_mode_tool()}

        if action == "music_control":
            sub = payload.get("action", "play")
            app = payload.get("app", "apple_music")
            if sub == "play":
                return {"result": self.music_controller.play_music_tool(app=app, genre=payload.get("genre", ""))}
            elif sub == "pause":
                return {"result": self.music_controller.pause_music_tool(app=app)}
            elif sub == "next":
                return {"result": self.music_controller.next_track_tool(app=app)}
            elif sub == "previous":
                return {"result": self.music_controller.previous_track_tool(app=app)}
            elif sub == "now_playing":
                return {"result": self.music_controller.get_now_playing_tool()}
            elif sub == "volume":
                return {"result": self.music_controller.set_volume_tool(level=payload.get("level", "50"))}
            return {"error": f"unknown music action: {sub}"}

        if action == "weather":
            city = payload.get("city", "")
            return {"result": self.weather_service.get_current_weather_tool(city=city)}

        if action == "llm_config_get":
            cfg = self.llm_config_store.load()
            return {"config": cfg, "chat_available": self.brain is not None}

        if action == "llm_config_set":
            cfg = self.llm_config_store.save(payload)
            # Recreate brain so new config takes effect immediately.
            try:
                self.brain = LLMBrain() if LLMBrain is not None else None
                return {"result": "saved", "config": cfg, "chat_available": self.brain is not None}
            except Exception as exc:
                self.brain = None
                return {"result": f"saved_with_error: {exc}", "config": cfg, "chat_available": False}

        if action == "llm_test":
            try:
                test_brain = LLMBrain() if LLMBrain is not None else None
                if test_brain is None:
                    return {"ok": False, "message": "LLM class unavailable"}

                text = test_brain.generate_text(
                    "请仅回复：连接成功",
                    system_instruction="You are a concise assistant.",
                )
                return {"ok": True, "message": text}
            except Exception as exc:
                return {"ok": False, "message": str(exc)}

        if action == "ollama_status":
            host = _ollama_host()
            binary = shutil.which("ollama")
            try:
                tags = _ollama_tags(host)
                models = [m.get("name", "") for m in tags.get("models", []) if m.get("name")]
                return {
                    "installed": bool(binary),
                    "host": host,
                    "running": True,
                    "models": models,
                }
            except Exception as exc:
                return {
                    "installed": bool(binary),
                    "host": host,
                    "running": False,
                    "models": [],
                    "message": str(exc),
                }

        if action == "ollama_start":
            host = _ollama_host()
            try:
                _ollama_tags(host, timeout_sec=1.0)
                return {"ok": True, "message": "Ollama service is already running.", "host": host}
            except Exception:
                pass

            binary = shutil.which("ollama")
            if binary:
                try:
                    subprocess.Popen(
                        [binary, "serve"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        start_new_session=True,
                    )
                except Exception as exc:
                    return {"ok": False, "message": f"Failed to start ollama serve: {exc}", "host": host}
            else:
                # Fallback for app installation where CLI may not be in PATH.
                try:
                    subprocess.Popen(
                        ["open", "-a", "Ollama"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        start_new_session=True,
                    )
                except Exception as exc:
                    return {"ok": False, "message": f"Ollama not found in PATH and app launch failed: {exc}", "host": host}

            for _ in range(12):
                try:
                    _ollama_tags(host, timeout_sec=1.0)
                    return {"ok": True, "message": "Ollama started successfully.", "host": host}
                except Exception:
                    import time

                    time.sleep(0.5)

            return {"ok": False, "message": "Start command sent, but Ollama API is not reachable yet.", "host": host}

        if action == "ollama_list_models":
            host = _ollama_host()
            try:
                tags = _ollama_tags(host, timeout_sec=4.0)
                models = [m.get("name", "") for m in tags.get("models", []) if m.get("name")]
                return {"ok": True, "models": models, "host": host}
            except Exception as exc:
                return {"ok": False, "models": [], "host": host, "message": str(exc)}

        if action == "ollama_pull_model":
            host = _ollama_host()
            model = (payload.get("model") or "").strip()
            if not model:
                return {"ok": False, "message": "model is required"}

            url = host + "/api/pull"
            try:
                response = requests.post(url, json={"name": model, "stream": False}, timeout=600)
                response.raise_for_status()
                return {"ok": True, "message": f"Model pulled: {model}", "result": response.json()}
            except Exception as exc:
                return {"ok": False, "message": str(exc)}

        if action == "ollama_run":
            host = _ollama_host()
            model = (payload.get("model") or "").strip()
            prompt = (payload.get("prompt") or "").strip()
            if not model or not prompt:
                return {"ok": False, "message": "model and prompt are required"}

            url = host + "/api/generate"
            body = {"model": model, "prompt": prompt, "stream": False}
            try:
                response = requests.post(url, json=body, timeout=240)
                response.raise_for_status()
                data = response.json()
                return {"ok": True, "response": data.get("response", ""), "raw": data}
            except Exception as exc:
                return {"ok": False, "message": str(exc)}

        return {"error": f"unknown action: {action}"}


def main():
    runtime = BridgeRuntime()

    for raw in sys.stdin:
        line = raw.strip()
        if not line:
            continue

        req_id = None
        try:
            req = json.loads(line)
            req_id = req.get("id")
            action = req.get("action")
            payload = req.get("payload") or {}

            result = runtime.handle(action, payload)
            response = {"id": req_id, "ok": "error" not in result, "result": result}
        except Exception as exc:
            response = {
                "id": req_id,
                "ok": False,
                "error": str(exc),
                "trace": traceback.format_exc(),
            }

        sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
