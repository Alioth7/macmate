import os
import signal
import sys
from core.llm_brain import LLMBrain
from tool.calendar_adapter import MacCalendarAdapter
from tool.memory_manager import MemoryManager
from tool.system_monitor import SystemMonitor
from tool.shell_executor import ShellExecutor
from tool.scene_profiles import SceneProfileManager
from tool.music_controller import MusicController
from tool.weather_service import WeatherService
from tool.scheduler import MacMateScheduler

# 初始化工具（这会触发 @registry.register）
adapter = MacCalendarAdapter()
# 初始化长期记忆模块
memory_manager = MemoryManager("./data")
# 初始化系统监控模块（注册工具并开始采样）
system_monitor = SystemMonitor("./data")
system_monitor.start_activity_watch(interval_sec=30)
# 初始化 Shell 执行器（默认 agent 模式）
shell_executor = ShellExecutor(mode="agent")
# 初始化场景预设
scene_profiles = SceneProfileManager()
# 初始化音乐控制
music_controller = MusicController()
# 初始化天气服务
weather_service = WeatherService()
# 初始化调度器
scheduler = MacMateScheduler()

def signal_handler(sig, frame):
    print('\n👋 Exiting MacMate...')
    scheduler.stop()
    sys.exit(0)

def main():
    brain = LLMBrain()

    # 注册每日简报任务（每晚 22:00）
    def nightly_briefing():
        try:
            prompt = "请根据今天的使用数据和日程，生成一份每日简报并保存。"
            brain.run_cycle(prompt)
            print("📝 每晚简报已自动生成。")
        except Exception as e:
            print(f"⚠️ 每晚简报生成失败: {e}")

    scheduler.register_daily_task(22, 0, "每日简报", nightly_briefing)

    print("🚀 MacMate 2.0 (ReAct Model) Started.")
    print("Supports: multi-step reasoning, self-correction, tools.")
    print(f"Shell security mode: {shell_executor._mode}")
    
    signal.signal(signal.SIGINT, signal_handler)

    while True:
        try:
            q = input("\n[Master]: ")
            if not q.strip(): continue
            if q.lower() in ['exit', 'quit']: break
            
            final_answer = brain.run_cycle(q)
            print(f"\n✅ Final Result: {final_answer}")
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    main()
