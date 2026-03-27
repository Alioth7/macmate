import json
import datetime
import requests
import re
import ast
from core.tools import registry
from core.llm_config import LLMConfigStore

class LLMBrain:
    def __init__(self):
        cfg_store = LLMConfigStore("./data/llm_config.json")
        cfg = cfg_store.load()

        self.config_store = cfg_store
        self._mode = cfg.get("mode", "api")  # api | ollama
        self.configured = False

        if self._mode == "ollama":
            host = cfg.get("ollama_host", "http://127.0.0.1:11434")
            self.api_url = f"{host.rstrip('/')}/api/chat"
            self.headers = {"Content-Type": "application/json"}
            self.model = cfg.get("ollama_model", "qwen2.5:7b")
            self.configured = True
        else:
            self.api_url = cfg.get("api_url", "")
            api_key = cfg.get("api_key", "")
            self.headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            self.model = cfg.get("api_model", "deepseek/deepseek-v3.2-251201")
            self.configured = bool(self.api_url and api_key)

        if not self.configured:
            print("\n" + "=" * 60)
            print("\u26a0\ufe0f  LLM \u672a\u914d\u7f6e\uff01\u8bf7\u5728 LLM Settings \u9762\u677f\u4e2d\u8bbe\u7f6e API URL/Key \u6216 Ollama\u3002")
            print("   \u914d\u7f6e\u6587\u4ef6: ./data/llm_config.json")
            print("=" * 60 + "\n")

        self.history = []
        self.system_prompt_str = self._build_system_prompt()
        self.history.append({"role": "system", "content": self.system_prompt_str})

    def _build_system_prompt(self):
        tools_desc = registry.get_descriptions()
        now = datetime.datetime.now()
        weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        now_str = f"{now.strftime('%Y-%m-%d %H:%M:%S')} ({weekdays[now.weekday()]})"
        
        # --- 自动读取长期记忆注入到潜意识 ---
        plans_context = "暂无"
        try:
            with open("data/long_term_plans.json", 'r', encoding='utf-8') as f:
                plans = json.load(f)
                active_plans = [p['content'] for p in plans if p.get('status') == 'active']
                if active_plans:
                    plans_context = "\n".join([f"- {job}" for job in active_plans])
        except:
            pass
        # ----------------------------------

        # --- weather context (non-blocking) ---
        weather_context = None
        try:
            from tool.weather_service import WeatherService
            _ws = WeatherService.__new__(WeatherService)
            _ws._default_city = ""
            _ws.WTTR_URL = WeatherService.WTTR_URL
            _ws.TIMEOUT = 3
            weather_context = _ws.get_weather_summary()
        except Exception:
            pass
        weather_line = f"\n当前天气: {weather_context}" if weather_context else ""
        # ----------------------------------

        return f"""
你是一个运行在 macOS 上的智能操作系统代理 (MacMate)。
你的能力覆盖：日历管理、长期记忆、系统监控、Shell 命令执行、场景切换、音乐控制、天气查询、定时提醒。
当前时间: {now_str}{weather_line}

【用户的核心长期目标 (Core Long-Term Goals)】:
{plans_context}
(请在所有决策和建议中，时刻考虑上述目标的影响)

可用工具 (Available Tools):
{tools_desc}

交互协议 (ReAct Protocol):
1. THOUGHT: 用中文思考并解释你的推理过程。这是关键步骤。
2. ACTION: 调用工具。格式: FUNCTION_NAME(param1="value", param2="value")
   - 每次只能调用一个工具 (ONE action per turn)。等待工具返回结果 (TOOL_OUTPUT)。
   - 严格遵守 Python 函数调用语法。
3. PAUSE: 等待工具执行。
4. ANSWER: 给用户的最终回复。如果你需要向用户提问、要求提供更多信息（如时间不明）或确认操作，请直接在此处输出问题，以等待用户下一步回答！严禁调用不存在的问询工具（如 ask_user 等）。

约束条件 (Constraints):
- **冲突检测**: 每当用户请求添加日程(add_calendar_event)时，你**必须**先调用 `get_calendar_events` 查看该时间段是否已有其他安排。如果冲突，请使用 ANSWER 先询问用户是否需要重叠安排。
- **智能重排 (Smart Rescheduling)**:
    - 遇到时间冲突时，请分析已有日程的**弹性**：
      - **刚性 (Inflexible)**: 固定会议、外部邀请、Deadline (通常有具体的人名及会议室)。--> 不可移动。
      - **弹性 (Flexible)**: 个人学习、健身、阅读、复盘 (通常是个人习惯或长期目标)。--> 可以延后或调整。
    - 策略：如果有新任务进来，优先**自动建议**将原有的【弹性任务】往后顺延，给【刚性任务】腾出时间。不要傻乎乎只说冲突了，请给出一个调整方案。
- **严禁捏造事实**。在删除日程前必须先查询日历。
- 如果用户说“删除今天所有会议”，请先调用 `get_calendar_events` 查看有哪些会议，然后循环调用删除工具，或者在脑海中规划好后逐个删除。
- 工具的时间参数格式必须是 "YYYY-MM-DD HH:MM"。
- **记忆功能 (Memory Feature)**: 
    - 当用户询问“总结”、“简报”、“建议”或“我该干什么”时，**必须**先调用 `get_past_daily_logs` (获取过去日志) 或 `get_long_term_plans` (获取长期目标) 来获取上下文。
    - 绝不要在没有上下文的情况下给建议。
    - 使用 `save_daily_summary` 来记录用户的重要进展或你的建议。
- **行为分析提醒 (Usage + Schedule Reminder)**:
    - 当用户询问“我今天效率怎么样”、“提醒我该专注了”、“结合日程分析我现在该做什么”时，优先调用 `sample_activity_usage` 和 `get_activity_usage_summary`。
    - 如果用户提供了日程 JSON（或你已查询到结构化事件），再调用 `analyze_schedule_reminders` 输出提醒建议。
- **Shell 命令安全协议**:
    - 调用 `run_shell_command` 前，**必须**在 THOUGHT 中写清楚即将执行的完整命令。
    - 如果工具返回“needs user confirmation”，你必须使用 ANSWER 询问用户是否确认执行。
    - 用户确认后，使用 `run_shell_command_confirmed` 执行。
    - **绝不**尝试绕过安全机制或拆分危险命令来规避检测。
- **音乐控制**:
    - 支持 Apple Music (apple_music) 和 网易云音乐 (netease)。
    - 如果用户没有指定平台，优先尝试 Apple Music。
    - 可以结合当前时间和天气信息推断用户心境，主动推荐适合的歌单。
- **场景预设**:
    - “专注模式”/ “开始工作” -> 调用 `activate_focus_mode`。
    - “休闲模式”/ “下班了” -> 调用 `activate_relax_mode`。

示例 (Example):
User: "我今天该干点什么？"
THOUGHT: 用户在寻求建议，我需要先查看他的长期目标和昨天的日志，看看进度如何。
ACTION: get_long_term_plans()
PAUSE
(System returns: 目标是学习 Python)
THOUGHT: 发现目标是学 Python，我再看看昨天的日志。
ACTION: get_past_daily_logs(days=1)
PAUSE
(System returns: 昨天复习了装饰器，觉得难)
ANSWER: 基于你“精通 Python”的目标，鉴于昨天觉得装饰器很难，今天建议你写几个实际的代码例子来巩固一下，不要只看书。
"""

    def clear_history(self):
        """清空当前对话历史并重置 system_prompt"""
        self.history = []
        self.system_prompt_str = self._build_system_prompt()
        self.history.append({"role": "system", "content": self.system_prompt_str})
        return True

    def generate_text(self, prompt, system_instruction=None):
        """Generate a simple text response without ReAct loop/tools."""
        if not self.configured:
            return "\u26a0\ufe0f LLM \u672a\u914d\u7f6e\u3002\u8bf7\u5148\u5728 LLM Settings \u4e2d\u8bbe\u7f6e API \u6216 Ollama \u914d\u7f6e\u3002"
        sys_prompt = system_instruction if system_instruction else "You are a helpful assistant."
        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": prompt}
        ]
        
        try:
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": 0.7 # Slightly creative for summaries
            }
            response = requests.post(self.api_url, headers=self.headers, json=payload, timeout=60)
            response.raise_for_status()
            result_json = response.json()
            return result_json['choices'][0]['message']['content']
        except Exception as e:
            return f"Error generating text: {e}"

    def run_cycle(self, user_input, max_steps=15, step_callback=None):
        """执行 ReAct 循环
        Args:
            user_input: 用户输入
            max_steps: 最大循环次数
            step_callback: 回调函数，参数为 (step_type, content)，用于UI更新
        """
        if not self.configured:
            msg = "\u26a0\ufe0f LLM \u672a\u914d\u7f6e\u3002\u8bf7\u5728 LLM Settings \u4e2d\u8bbe\u7f6e API URL/Key \u6216\u914d\u7f6e Ollama\uff0c\u7136\u540e\u91cd\u542f\u5e94\u7528\u3002"
            if step_callback:
                step_callback("error", msg)
            return msg
        # 更新时间戳（重新生成 system prompt）但保留之前的 conversation history
        current_sys_prompt = self._build_system_prompt()
        # 如果 history 为空或者第一条不是最新的 system prompt
        if not self.history:
            self.history.append({"role": "system", "content": current_sys_prompt})
        else:
            self.history[0] = {"role": "system", "content": current_sys_prompt}

        self.history.append({"role": "user", "content": user_input})

        print(f"🧠 Agent Activation... [Model: {self.model}]")
        if step_callback: step_callback("status", f"🧠 Agent Activation... [Model: {self.model}]")

        for step in range(max_steps):
            print(f"🔄 Step {step + 1}...")
            
            # 调用 API
            try:
                payload = {
                    "model": self.model,
                    "messages": self.history,
                    "temperature": 0.1
                }
                response = requests.post(self.api_url, headers=self.headers, json=payload, timeout=60)
                response.raise_for_status()
                result_json = response.json()
                content = result_json['choices'][0]['message']['content']
            except Exception as e:
                err_msg = f"API Error: {e}"
                if step_callback: step_callback("error", err_msg)
                # 即使 API 报错，也需要清理本地状态，返回错误让 UI 停止转圈
                return f"抱歉，连接模型时遇到错误: {err_msg}"

            self.history.append({"role": "assistant", "content": content})
            if step_callback: step_callback("raw_response", content)

            # 归一化标签大小写（防止模型输出 [answer] 或 Answer: 等非标准格式，并兼容全角冒号）
            orig_content = content
            content = content.replace("：", ":")  # 先将其余所有可能的中文冒号转为英文冒号
            content = content.replace("Answer:", "ANSWER:").replace("answer:", "ANSWER:")
            content = content.replace("[ANSWER]", "ANSWER:").replace("[answer]", "ANSWER:")
            content = content.replace("Thought:", "THOUGHT:").replace("thought:", "THOUGHT:")
            content = content.replace("[THOUGHT]", "THOUGHT:").replace("[thought]", "THOUGHT:")
            content = content.replace("Action:", "ACTION:").replace("action:", "ACTION:")

            # 解析 THOUGHT (通常在 ACTION 前面)
            thought = ""
            if "THOUGHT:" in content:
                # 寻找 THOUGHT: 标签
                parts = content.split("THOUGHT:", 1)
                if len(parts) > 1:
                    thought_content = parts[1]
                    # 如果后面有 ACTION: 或 ANSWER:，截断到那里
                    if "ACTION:" in thought_content:
                        thought = thought_content.split("ACTION:")[0].strip()
                    elif "ANSWER:" in thought_content:
                        thought = thought_content.split("ANSWER:")[0].strip()
                    else:
                        thought = thought_content.strip()
                    
                if step_callback: step_callback("thought", thought)

            # 检查是否有 ANSWER (终结符)
            if "ANSWER:" in content:
                # 提取 ANSWER: 之后的所有内容
                answer = content.split("ANSWER:", 1)[1].strip()
                if step_callback: step_callback("answer", answer)
                return answer
            
            # 检查是否有 ACTION
            if "ACTION:" in content:
                try:
                    # 提取 ACTION 代码行
                    lines = content.split('\n')
                    action_line = None
                    for line in lines:
                        if "ACTION:" in line:
                            # Split carefully to avoid splitting inside strings if possible, but simplicity first
                            action_line = line.split("ACTION:", 1)[1].strip()
                            break
                    
                    if not action_line: continue

                    if step_callback: step_callback("action_call", action_line)

                    # 使用 AST 解析来安全获取函数名和参数
                    try:
                        tree = ast.parse(action_line)
                    except SyntaxError:
                         self.history.append({"role": "user", "content": "ERROR: Invalid function call syntax."})
                         if step_callback: step_callback("error", "Invalid function call syntax.")
                         continue
                    
                    if not tree.body or not isinstance(tree.body[0], ast.Expr) or not isinstance(tree.body[0].value, ast.Call):
                         self.history.append({"role": "user", "content": "ERROR: Invalid function call syntax."})
                         continue

                    call_node = tree.body[0].value
                    
                    # 获取函数名
                    func_name = ""
                    if isinstance(call_node.func, ast.Name):
                        func_name = call_node.func.id
                    elif isinstance(call_node.func, ast.Attribute):
                         func_name = call_node.func.attr 
                    
                    tool_func = registry.get_tool(func_name)
                    if not tool_func:
                        self.history.append({"role": "user", "content": f"ERROR: Tool '{func_name}' not registered."})
                        if step_callback: step_callback("error", f"Tool '{func_name}' not registered.")
                        continue

                    # 提取参数
                    kwargs = {}
                    arg_error = False
                    for kw in call_node.keywords:
                        try:
                            # 尝试解析字面量
                            val = ast.literal_eval(kw.value)
                            kwargs[kw.arg] = val
                        except:
                            self.history.append({"role": "user", "content": f"ERROR: Argument '{kw.arg}' must be a literal value."})
                            arg_error = True
                            break
                    
                    if arg_error: continue

                    print(f"🔧 Tool Call: {func_name} | Args: {kwargs}")
                    
                    if step_callback: step_callback("tool_executing", f"Executing {func_name}...")

                    # 执行工具
                    try:
                        # 确保传给工具的都是字符串，防止 AST 解析出数字导致 wrapper 里的 split fail
                        # 但如果工具本身有类型注解且兼容数字则没问题。目前的 wrapper 似乎假设是 string (split(':'))
                        # 检查 calendar_adapter 里的 add_event_tool，确实有 split(':')，所以我们需要转 string
                        # 为了保险，把所有 kwargs 转 string？不，应该由 adapter 处理，或这里统一转
                        # 刚才 adapter 里的 add_event_tool 有类型注解 str。
                        # ast.literal_eval 可能返回 int。
                        # 我们可以在这里做个简单的转换
                        for k, v in kwargs.items():
                             if isinstance(v, (int, float)):
                                  kwargs[k] = str(v)

                        tool_result = tool_func(**kwargs)
                    except TypeError as e:
                        tool_result = f"Argument Error: {e}"
                    except Exception as e:
                        tool_result = f"Runtime Error: {e}"
                        
                    print(f"📝 Output: {tool_result}")
                    self.history.append({"role": "user", "content": f"TOOL_OUTPUT: {tool_result}"})
                    if step_callback: step_callback("observation", tool_result)

                except Exception as e:
                    print(f"❌ Execution Error: {e}")
                    if step_callback: step_callback("error", f"Execution Error: {e}")
                    # 如果工具执行出错，也要给模型一个反馈，防止它卡在那一直加载
                    self.history.append({"role": "user", "content": f"TOOL_ERROR: {e}"})
                    continue 
            else:
                # 既没有 ACTION 也没有严格的 ANSWER:，很可能是模型忘记写前缀直接输出了回复。
                # 我们可以把剔除 THOUGHT 的剩余部分作为 final answer 返回。
                final_answer = content
                if "THOUGHT:" in content:
                    # 如果这句本身有 THOUGHT:，说明它可能在后面直接写了回复文字，却没有加 ANSWER:
                    # 我们把 thought_parts 去掉 thought 的末尾剩余文本提取出来
                    thought_parts = content.split("THOUGHT:", 1)[1]
                    remaining = thought_parts.replace(thought, "", 1).strip()
                    if remaining:
                        final_answer = remaining
                    else:
                        final_answer = thought # fallback to thought if literally nothing else
                        
                if not final_answer:
                    final_answer = content.strip()
                    
                if step_callback: step_callback("answer", final_answer)
                return final_answer
        
        return "Mission aborted: Too many steps."

    def classify_events(self, events_text):
        """Ask LLM to classify events into Eisenhower Matrix coordinates."""
        prompt = f"""
请分析以下待办事项/日程，并按照【艾森豪威尔矩阵】（四象限法则）进行分类。
输入内容:
{events_text}

请返回一个纯 JSON 列表，格式如下：
[
  {{"title": "事件标题", "urgency": 1-10, "importance": 1-10, "quadrant": "Q1/Q2/Q3/Q4", "description": "简短说明"}}
]
Urgency (紧急性): 10 为最紧急。
Importance (重要性): 10 为最重要。
Quadrant:
Q1: 紧急且重要 (Do First)
Q2: 重要但不紧急 (Schedule)
Q3: 紧急但不重要 (Delegate)
Q4: 不紧急也不重要 (Delete)

仅返回 JSON，不要 Markdown 代码块。
"""
        messages = [{"role": "user", "content": prompt}]
        try:
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": 0.1
            }
            response = requests.post(self.api_url, headers=self.headers, json=payload, timeout=60)
            response.raise_for_status()
            content = response.json()['choices'][0]['message']['content']
            # 清理可能的 markdown
            content = content.replace("```json", "").replace("```", "").strip()
            return json.loads(content)
        except Exception as e:
            return [{"title": "Error parsing", "urgency": 0, "importance": 0, "quadrant": "Error", "description": str(e)}]

