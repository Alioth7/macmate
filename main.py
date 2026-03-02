import os
import signal
import sys
from core.llm_brain import LLMBrain
from tool.calendar_adapter import MacCalendarAdapter
from tool.memory_manager import MemoryManager

# 初始化工具（这会触发 @registry.register）
adapter = MacCalendarAdapter()
# 初始化长期记忆模块
memory_manager = MemoryManager("./data")

def signal_handler(sig, frame):
    print('\n👋 Exiting MacMate...')
    sys.exit(0)

def main():
    brain = LLMBrain()
    
    print("🚀 MacMate 2.0 (ReAct Model) Started.")
    print("Supports: multi-step reasoning, self-correction, tools.")
    
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
