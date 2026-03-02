import json
import datetime
import requests
import re
import config
import ast
from core.tools import registry

class LLMBrain:
    def __init__(self):
        self.api_url = config.API_URL
        self.headers = {
            "Authorization": f"Bearer {config.API_KEY}",
            "Content-Type": "application/json"
        }
        # 修改为用户指定的 DeepSeek V3.2 模型 ID
        self.model = "deepseek/deepseek-v3.2-251201" 
        self.history = []
        self.system_prompt_str = self._build_system_prompt()
        self.history.append({"role": "system", "content": self.system_prompt_str})

    def _build_system_prompt(self):
        tools_desc = registry.get_descriptions()
        now = datetime.datetime.now()
        weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        now_str = f"{now.strftime('%Y-%m-%d %H:%M:%S')} ({weekdays[now.weekday()]})"
        
        return f"""
你是一个运行在 macOS 上的智能操作系统代理 (MacMate)。
你现在可以使用 [日历/Calendar] 和 [长期记忆/Long-Term Memory] 工具。
当前时间: {now_str}

可用工具 (Available Tools):
{tools_desc}

交互协议 (ReAct Protocol):
1. THOUGHT: 用中文思考并解释你的推理过程。这是关键步骤。
2. ACTION: 调用工具。格式: FUNCTION_NAME(param1="value", param2="value")
   - 每次只能调用一个工具 (ONE action per turn)。
   - 等待工具返回结果 (TOOL_OUTPUT)。
   - 严格遵守 Python 函数调用语法。
3. PAUSE: 等待工具执行。
4. ANSWER: 给用户的最终回复。

约束条件 (Constraints):
- **严禁捏造事实**。在删除日程前必须先查询日历。
- 如果用户说“删除今天所有会议”，请先调用 `get_calendar_events` 查看有哪些会议，然后循环调用删除工具，或者在脑海中规划好后逐个删除。
- 工具的时间参数格式必须是 "YYYY-MM-DD HH:MM"。
- **记忆功能 (Memory Feature)**: 
    - 当用户询问“总结”、“简报”、“建议”或“我该干什么”时，**必须**先调用 `get_past_daily_logs` (获取过去日志) 或 `get_long_term_plans` (获取长期目标) 来获取上下文。
    - 绝不要在没有上下文的情况下给建议。
    - 使用 `save_daily_summary` 来记录用户的重要进展或你的建议。

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

    def run_cycle(self, user_input, max_steps=15):
        """执行 ReAct 循环"""
        # 更新时间戳（重新生成 system prompt）但保留之前的 conversation history
        current_sys_prompt = self._build_system_prompt()
        # 如果 history 为空或者第一条不是最新的 system prompt
        if not self.history:
            self.history.append({"role": "system", "content": current_sys_prompt})
        else:
            self.history[0] = {"role": "system", "content": current_sys_prompt}

        self.history.append({"role": "user", "content": user_input})

        print(f"🧠 Agent Activation... [Model: {self.model}]")

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
                return f"API Error: {e}"

            print(f"🤖 Agent:\n{content}\n")
            self.history.append({"role": "assistant", "content": content})

            if "ANSWER:" in content:
                # 兼容有时候 ANSWER: 在中间的情况，以及多行输出
                ans_parts = content.split("ANSWER:")
                if len(ans_parts) > 1:
                     return ans_parts[1].strip()
                return content # Fallback

            if "ACTION:" in content:
                try:
                    # 提取 ACTION 代码行
                    # 只能处理单行 Action 调用
                    lines = content.split('\n')
                    action_line = None
                    for line in lines:
                        if "ACTION:" in line:
                            action_line = line
                            break
                    
                    if not action_line: continue

                    # 去掉 ACTION: 前缀
                    func_call_str = action_line.replace("ACTION:", "").strip()
                    
                    # 使用 AST 解析来安全获取函数名和参数
                    # 这是一个非常简化的 AST 处理，假设 LLM 输出的是合法的 Python 函数调用
                    tree = ast.parse(func_call_str)
                    
                    if not tree.body or not isinstance(tree.body[0], ast.Expr) or not isinstance(tree.body[0].value, ast.Call):
                         self.history.append({"role": "user", "content": "ERROR: Invalid function call syntax."})
                         continue

                    call_node = tree.body[0].value
                    
                    # 获取函数名
                    func_name = ""
                    if isinstance(call_node.func, ast.Name):
                        func_name = call_node.func.id
                    elif isinstance(call_node.func, ast.Attribute):
                         func_name = call_node.func.attr # 支持 self.xxx 但这里工具通常是顶层名
                    
                    tool_func = registry.get_tool(func_name)
                    if not tool_func:
                        self.history.append({"role": "user", "content": f"ERROR: Tool '{func_name}' not registered."})
                        continue

                    # 提取参数
                    kwargs = {}
                    for kw in call_node.keywords:
                        try:
                            # 尝试解析字面量 (字符串, 数字, None, True/False)
                            val = ast.literal_eval(kw.value)
                            kwargs[kw.arg] = val
                        except:
                            # 如果参数是变量名或表达式，ast.literal_eval 会失败
                            # 这种情况下，简单的办法是把 value 节点转回源码字符串
                            # 但为了安全和简单，我们这里捕获异常并跳过，或者提示 LLM 使用字面量
                            self.history.append({"role": "user", "content": f"ERROR: Argument '{kw.arg}' must be a literal value (string/number), not variable."})
                            raise ValueError(f"Argument '{kw.arg}' is not a literal.")

                    print(f"🔧 Tool Call: {func_name} | Args: {kwargs}")
                    
                    # 执行工具
                    try:
                        tool_result = tool_func(**kwargs)
                    except TypeError as e:
                        tool_result = f"Argument Error: {e}"
                    except Exception as e:
                        tool_result = f"Runtime Error: {e}"
                        
                    print(f"📝 Output: {tool_result}")
                    self.history.append({"role": "user", "content": f"TOOL_OUTPUT: {tool_result}"})

                except Exception as e:
                    print(f"❌ Execution Error: {e}")
                    # 不要在这里 append，因为如果不 break 会导致死循环或者逻辑混乱
                    # 下一轮 LLM 会看到这一条
                    pass 
            else:
                # 没有任何 Action 和 Answer 的思考过程
                pass
        
        return "Mission aborted: Too many steps."
