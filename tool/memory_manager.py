import os
import json
import datetime
from core.tools import registry

class MemoryManager:
    def __init__(self, data_dir="data"):
        self.data_dir = data_dir
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
        
        # 绑定工具实例到注册表
        registry.bind_instance(self)
        
        self.plans_file = os.path.join(data_dir, "long_term_plans.json")
        self.daily_logs_file = os.path.join(data_dir, "daily_logs.json")
        
        # 初始化文件
        if not os.path.exists(self.plans_file):
            with open(self.plans_file, 'w', encoding='utf-8') as f:
                json.dump([], f)
        
        if not os.path.exists(self.daily_logs_file):
            with open(self.daily_logs_file, 'w', encoding='utf-8') as f:
                json.dump([], f)

    @registry.register("add_long_term_plan", "Add a new long-term plan/goal. Args: content(str), custom_prompt(str optional), target_date(str 'YYYY-MM-DD' optional)")
    def add_plan(self, content: str, custom_prompt: str = "", target_date: str = "") -> str:
        try:
            with open(self.plans_file, 'r', encoding='utf-8') as f:
                plans = json.load(f)
            
            new_plan = {
                "id": len(plans) + 1,
                "content": content,
                "custom_prompt": custom_prompt,
                "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "target_date": target_date,
                "status": "active"
            }
            plans.append(new_plan)
            
            with open(self.plans_file, 'w', encoding='utf-8') as f:
                json.dump(plans, f, ensure_ascii=False, indent=2)
                
            return f"Success: Long-term plan added. ID: {new_plan['id']}"
        except Exception as e:
            return f"Error adding plan: {e}"

    @registry.register("get_long_term_plans", "Get all long-term plans. No args.")
    def get_plans(self) -> str:
        try:
            with open(self.plans_file, 'r', encoding='utf-8') as f:
                plans = json.load(f)
            
            if not plans:
                return "No long-term plans found."
            
            result = "Current Long-Term Plans:\n"
            for p in plans:
                status = p.get('status', 'active')
                target = f" (Target: {p.get('target_date')})" if p.get('target_date') else ""
                created = p.get('created_at', '')
                result += f"- [ID: {p['id']}] {p['content']}{target} (Created: {created}) [{status}]\n"
            return result
        except Exception as e:
            return f"Error reading plans: {e}"

    def get_plans_data(self) -> list:
        """Helper for UI to get raw list of plans."""
        try:
            if not os.path.exists(self.plans_file):
                return []
            with open(self.plans_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []

    def get_logs_data(self) -> list:
        """Helper for UI to get raw list of logs."""
        try:
            if not os.path.exists(self.daily_logs_file):
                return []
            with open(self.daily_logs_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []

    @registry.register("save_daily_summary", "Save a daily summary/log. Args: date(str 'YYYY-MM-DD'), summary(str), suggestions(str)")
    def save_daily_log(self, date: str, summary: str, suggestions: str) -> str:
        try:
            with open(self.daily_logs_file, 'r', encoding='utf-8') as f:
                logs = json.load(f)
            
            # 覆盖当天的 log 如果存在
            logs = [log for log in logs if log.get('date') != date]
            
            new_log = {
                "date": date,
                "summary": summary,
                "suggestions": suggestions,
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            logs.append(new_log)
            
            # 保持只存储最近 30 天
            logs.sort(key=lambda x: x['date'])
            if len(logs) > 30:
                logs = logs[-30:]
                
            with open(self.daily_logs_file, 'w', encoding='utf-8') as f:
                json.dump(logs, f, ensure_ascii=False, indent=2)
                
            return f"Success: Daily summary for {date} saved."
        except Exception as e:
            return f"Error saving log: {e}"

    @registry.register("get_past_daily_logs", "Get past daily logs. Args: days(int default=3)")
    def get_logs(self, days: int = 3) -> str:
        try:
            with open(self.daily_logs_file, 'r', encoding='utf-8') as f:
                logs = json.load(f)
            
            if not logs:
                return "No historical logs found."
            
            # 获取最近的 n 条
            recent_logs = logs[-days:]
            result = "Recent Daily Logs:\n"
            for log in recent_logs:
                result += f"=== Date: {log['date']} ===\nSummary: {log['summary']}\nSuggestions: {log['suggestions']}\n\n"
            return result
        except Exception as e:
            return f"Error reading logs: {e}"
