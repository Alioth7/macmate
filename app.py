import streamlit as st
import time
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from core.llm_brain import LLMBrain
from tool.calendar_adapter import MacCalendarAdapter
from tool.memory_manager import MemoryManager
from core.tools import registry
import datetime

# Page Config
st.set_page_config(
    page_title="MacMate AI Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize Session State
if "brain" not in st.session_state:
    # Initialize tools first
    adapter = MacCalendarAdapter()
    st.session_state.adapter = adapter # Save adapter instance
    memory_manager = MemoryManager("./data")
    st.session_state.memory_manager = memory_manager
    # Initialize Brain
    st.session_state.brain = LLMBrain()
    st.session_state.messages = [{"role": "assistant", "content": "你好！我是你的 MacMate 智能助手。有什么我可以帮你的吗？"}]

if "memory_manager" not in st.session_state:
    st.session_state.memory_manager = MemoryManager("./data")

# Function for Agent Callback to update UI
def agent_callback(step_type, content, container=None):
    """
    Handles updates from the LLM Brain during execution.
    We'll render these progressively.
    """
    if not container:
        container = st.empty()


    if step_type == "thought":
        container.markdown(f"🤔 **思考**:\n{content}")
    elif step_type == "action_call":
        container.code(f"🔨 调用工具: {content}", language="python")
    elif step_type == "observation":
        container.markdown(f"📝 **工具返回**:\n```\n{content}\n```")
    elif step_type == "error":
        container.error(content)
    elif step_type == "answer":
        # Final answer is handled by return value usually, but we can print it
        pass

# Sidebar
with st.sidebar:
    st.title("🤖 MacMate Control")
    st.markdown("---")
    if st.button("清除对话历史"):
        st.session_state.brain.history = []
        st.session_state.messages = [{"role": "assistant", "content": "记忆已清除。"}]
        st.rerun()
    
    st.markdown("### 模型信息")
    st.info(f"Using: {st.session_state.brain.model}")

# Main Interface
st.title("MacMate Intelligent Workspace")

tab1, tab2, tab3, tab4, tab5 = st.tabs(["💬 智能对话 (Chat)", "📅 日历视图 (Calendar)", "🧠 四象限分析 (Quadrant)", "🎯 长期规划 (Plan)", "📝 每日总结 (Daily)"])

# --- TAB 1: Chat Interface ---
with tab1:
    # Display chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat Input
    if prompt := st.chat_input("输入指令 (例如: '帮我在这个周五下午3点安排代码审查')..."):
        # Add user message to state
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Run Agent
        with st.chat_message("assistant"):
            st_callback_container = st.status("MacMate 正在思考...", expanded=True)
            
            # Define a local callback that writes to the status container
            def local_callback(t, c):
                # Using st.write inside the status container
                if t == "thought":
                    st_callback_container.write(f"🤔 **思考**: {c}")
                elif t == "action_call":
                    st_callback_container.write(f"🔨 **调用**: `{c}`")
                elif t == "observation":
                    st_callback_container.write(f"📝 **结果**: \n```\n{c}\n```")
                elif t == "error":
                    st_callback_container.error(c)

            # Execution
            # [System Hint] Force tool usage to avoid hallucination
            prompt_with_hint = prompt + " (System Note: If the user asks for an action like adding/checking calendar, you MUST call the tool. Do NOT simulate the result textually.)"
            final_response = st.session_state.brain.run_cycle(prompt_with_hint, step_callback=local_callback)
            
            st_callback_container.update(label="执行完成", state="complete", expanded=False)
            st.markdown(f"**{final_response}**")
        
        # Add final response text to history
        st.session_state.messages.append({"role": "assistant", "content": final_response})

# --- TAB 2: Calendar View ---
with tab2:
    st.header("你的最近日程")
    if st.button("刷新日历"):
        with st.spinner("Loading..."):
            pass # just rerun to refresh

    if "adapter" in st.session_state:
        adapter = st.session_state.adapter
        
        # 1. Fetch JSON data
        try:
            # Safe date calculation
            now = datetime.datetime.now()
            start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
            now_str = start_of_day.strftime("%Y-%m-%d %H:%M")
            
            # Use explicit timedelta
            delta = datetime.timedelta(days=14)
            future_date = now + delta
            end_str = future_date.strftime("%Y-%m-%d %H:%M")
            
            # 使用新写的 get_detailed_events 获取结构化数据 (Tool already returns structured list thanks to last upgrade)
            events_data = adapter.get_detailed_events(start_time=now_str, end_time=end_str)
            
            if events_data:
                df = pd.DataFrame(events_data)
                
                # --- A. Render "Clean" Course Schedule (Plotly Vertical Bar) ---
                st.subheader("🗓️ 周日程表 (24h 课程表视图)")
                
                # 1. Prepare Data
                # Convert strings to datetime for calculation
                df["Start_DT"] = pd.to_datetime(df["Start"])
                df["Finish_DT"] = pd.to_datetime(df["Finish"])
                
                # Create "Day" column for X-axis (e.g. "Mon 03-06")
                # Sort by date
                df = df.sort_values("Start_DT")
                df["Day"] = df["Start_DT"].dt.strftime("%m-%d\n%A") 
                
                # Math for Vertical Bars: Base = Start Hour, Y = Duration
                # We map 00:00 to 0.0, 08:30 to 8.5
                df["Start_Hour"] = df["Start_DT"].dt.hour + df["Start_DT"].dt.minute / 60.0
                duration_seconds = (df["Finish_DT"] - df["Start_DT"]).dt.total_seconds()
                df["Duration_Hours"] = duration_seconds / 3600.0
                
                # 2. Build Plotly Graph Object
                fig = go.Figure()

                # Add main bars
                fig.add_trace(go.Bar(
                    x=df["Day"],
                    y=df["Duration_Hours"],
                    base=df["Start_Hour"],
                    text=df["Task"],
                    textposition="inside",
                    texttemplate="%{text}<br>(%{y:.1f}h)",
                    hovertemplate="<b>%{text}</b><br>Start: %{base:.2f}<br>Duration: %{y:.2f}h<extra></extra>",
                    marker_color="rgba(55, 128, 191, 0.7)",
                    marker_line_width=0,
                    width=0.8,
                    showlegend=False
                ))

                # 3. Custom "Axis Line" Layout
                # Reverse Y axis so 00:00 is at top, 24:00 at bottom
                fig.update_layout(
                    height=800,
                    plot_bgcolor="white",
                    xaxis=dict(
                        title="",
                        showgrid=True, # Vertical Grid Lines (Day separators)
                        gridcolor="rgba(0,0,0,0.1)",
                        linecolor="rgba(0,0,0,0.1)",
                        tickmode="linear",
                        type="category" # Ensure days are treated as categories
                    ),
                    yaxis=dict(
                        title="",
                        range=[24, 0], # 0 at top, 24 at bottom
                        tickmode="array",
                        tickvals=list(range(0, 25)),
                        ticktext=[f"{h:02d}:00" for h in range(0, 25)],
                        showgrid=False, # NO Horizontal Grid Lines! Only pure axis ticks.
                        zeroline=False,
                        linecolor="rgba(0,0,0,0.1)"
                    ),
                    margin=dict(l=50, r=20, t=10, b=20)
                )

                # 4. Add "Current Time" Red Line across the chart
                now_dt = datetime.datetime.now()
                # Only if today is in the range displayed?
                # Plotly hline spans entire X axis, which is fine for "Current Time of Day"
                if 0 <= now_dt.hour < 24:
                    current_y = now_dt.hour + now_dt.minute / 60.0
                    fig.add_hline(
                        y=current_y, 
                        line_color="red", 
                        line_dash="dot",
                        line_width=1,
                        annotation_text="Now",
                        annotation_position="bottom right"
                    )

                st.plotly_chart(fig, use_container_width=True)
                
                st.divider()

                # --- B. Edit Single Event ---
                st.subheader("✏️ 修改日程 (Edit Event)")
                
                # Select Event
                event_titles = df["Task"].unique().tolist()
                selected_event_title = st.selectbox("选择要修改的事件", event_titles)
                
                if selected_event_title:
                    # Get current values (take the first match if multiple same titles, ideally should filter by time too)
                    # For simplicity, we filter by title, and if multiple, let user pick specific instance?
                    # Here we take the first matching row for basic implementation.
                    current_event_rows = df[df["Task"] == selected_event_title]
                    
                    # If multiple events with same title, show distinct start times
                    selected_row = current_event_rows.iloc[0]
                    if len(current_event_rows) > 1:
                         # Let user disambiguate by start time
                         time_options = current_event_rows["Start"].tolist()
                         selected_time = st.selectbox("该标题有多个时段，请选择开始时间", time_options)
                         selected_row = current_event_rows[current_event_rows["Start"] == selected_time].iloc[0]
                    
                    current_event = selected_row

                    c1, c2 = st.columns(2)
                    with c1:
                        # Convert string back to datetime for date_input/time_input
                        start_dt_obj = pd.to_datetime(current_event["Start"])
                        new_start_date = st.date_input("开始日期", value=start_dt_obj.date())
                        new_start_time = st.time_input("开始时间", value=start_dt_obj.time())
                        
                    with c2:
                        end_dt_obj = pd.to_datetime(current_event["Finish"])
                        new_end_date = st.date_input("结束日期", value=end_dt_obj.date())
                        new_end_time = st.time_input("结束时间", value=end_dt_obj.time())

                    # Combine
                    new_start_str = f"{new_start_date} {new_start_time.strftime('%H:%M')}"
                    new_end_str = f"{new_end_date} {new_end_time.strftime('%H:%M')}"
                    
                    if st.button("🔄 更新并同步到 MacOS 日历"):
                        # Call update tool
                        with st.spinner("Syncing to MacOS Calendar..."):
                            res = adapter.update_event_time(
                                title=selected_event_title,
                                old_start_str=current_event["Start"], # Use original start as ID
                                new_start_str=new_start_str,
                                new_end_str=new_end_str
                            )
                        
                        if "Success" in res:
                            st.success(res)
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(res)

            else:
                st.info("未来 14 天没有日程。")
        except Exception as e:
            import traceback
            st.error(f"Error fetching detailed calendar: {e}")
            st.code(traceback.format_exc())
    else:
        st.warning("日历适配器未初始化，请刷新页面。")

# --- TAB 3: Quadrant Analysis ---
with tab3:
    st.header("⚡️ 艾森豪威尔矩阵")
    st.markdown("让 AI 帮你分析哪些事情重要，哪些事情紧急。")
    
    if st.button("开始分析 (基于未来7天日程)"):
        with st.spinner("正在读取日历并进行 AI 分析..."):
            # 1. Get events
            get_events_func = registry.get_tool("get_calendar_events")
            if get_events_func:
                now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                end_str = (datetime.datetime.now() + datetime.timedelta(days=7)).strftime("%Y-%m-%d %H:%M")
                events_text = get_events_func(start_time=now_str, end_time=end_str)
                
                # 2. Call Brain to classify
                classified_data = st.session_state.brain.classify_events(events_text)
                
                if classified_data:
                    df = pd.DataFrame(classified_data)
                    
                    # 3. Plot
                    if not df.empty and "importance" in df.columns:
                        fig = px.scatter(
                            df, 
                            x="urgency", 
                            y="importance", 
                            text="title",
                            color="quadrant",
                            size_max=60,
                            hover_data=["description"],
                            title="任务四象限分布",
                            labels={"urgency": "紧急性 (Urgency)", "importance": "重要性 (Importance)"},
                            range_x=[0, 11],
                            range_y=[0, 11]
                        )
                        
                        # Add quadrant lines
                        fig.add_hline(y=5.5, line_dash="dash", line_color="gray")
                        fig.add_vline(x=5.5, line_dash="dash", line_color="gray")
                        
                        # Annotations for quadrants
                        fig.add_annotation(x=2.5, y=8, text="Q1: do First", showarrow=False, opacity=0.3, font_size=20)
                        fig.add_annotation(x=8, y=8, text="Q2: Schedule", showarrow=False, opacity=0.3, font_size=20)
                        fig.add_annotation(x=2.5, y=2.5, text="Q3: Delegate", showarrow=False, opacity=0.3, font_size=20)
                        fig.add_annotation(x=8, y=2.5, text="Q4: Delete", showarrow=False, opacity=0.3, font_size=20)
                        
                        st.plotly_chart(fig, use_container_width=True)
                        
                        st.markdown("### 详细建议列表")
                        st.table(df[["title", "quadrant", "description"]])
                    else:
                        st.warning("未能解析出有效任务数据。")
                else:
                    st.error("AI 分析失败。")

# --- TAB 4: Long Term Planning ---
with tab4:
    st.header("🎯 长期规划与目标")
    
    # 1. Display Plans
    # Ensure memory_manager is in session_state (it should be from init)
    if "memory_manager" in st.session_state:
        mm = st.session_state.memory_manager
        plans_data = mm.get_plans_data()
        
        if plans_data:
            df_plans = pd.DataFrame(plans_data)
            # Reorder columns for display if possible
            desired_cols = ["id", "content", "custom_prompt", "target_date", "status", "created_at"]
            # Filter to columns that actually exist
            display_cols = [c for c in desired_cols if c in df_plans.columns]
            # Add any other columns that might exist
            other_cols = [c for c in df_plans.columns if c not in display_cols]
            final_cols = display_cols + other_cols
            
            st.dataframe(df_plans[final_cols], use_container_width=True, hide_index=True)
        else:
            st.info("暂无长期规划。")

        st.subheader("➕ 添加新目标")
        with st.form("new_plan_form"):
            new_plan_content = st.text_input("目标内容", placeholder="例如：学习 Python 进阶")
            new_plan_prompt = st.text_area("自定义提示词 (Context/Prompt)", placeholder="例如：请时刻提醒我要保持代码简洁，或者这是我的作息时间表...", height=100)
            new_plan_date = st.date_input("目标日期", value=None)
            submitted = st.form_submit_button("添加目标")
            
            if submitted and new_plan_content:
                date_str = new_plan_date.strftime("%Y-%m-%d") if new_plan_date else ""
                # Update signature call
                res = mm.add_plan(new_plan_content, custom_prompt=new_plan_prompt, target_date=date_str)
                st.success(res)
                time.sleep(1)
                st.rerun()
    else:
        st.error("Memory Manager not initialized.")

# --- TAB 5: Daily Summary ---
with tab5:
    st.header("📝 每日总结与反思")
    
    if "memory_manager" in st.session_state:
        mm = st.session_state.memory_manager
        
        # 1. Write Summary
        st.subheader("✍️ 今日总结")
        
        # AI Generator Button
        col_ai, col_dummy = st.columns([1, 4])
        with col_ai:
            if st.button("🤖 AI 生成草稿"):
                with st.spinner("正在读取日历并生成总结..."):
                    # 1. Get Calendar Data
                    if "adapter" in st.session_state:
                         # Get today's events from start to end of day
                         now = datetime.datetime.now()
                         start_of_day = now.replace(hour=0, minute=0, second=0).strftime("%Y-%m-%d %H:%M")
                         end_of_day = now.replace(hour=23, minute=59, second=59).strftime("%Y-%m-%d %H:%M")
                         events = st.session_state.adapter.get_detailed_events(start_of_day, end_of_day)
                         
                         event_text = json.dumps(events, ensure_ascii=False) if events else "今天没有日历事件。"
                         
                         # 2. Get Long Term Plans Context
                         plans_context = ""
                         raw_plans = mm.get_plans_data()
                         for p in raw_plans:
                             if p.get('status') == 'active':
                                 plans_context += f"- 目标: {p['content']}\n"
                                 if p.get('custom_prompt'):
                                     plans_context += f"  > 上下文/指导原则: {p['custom_prompt']}\n"
                         
                         # 3. Call LLM
                         prompt = f"""
                         请根据今天的日程和我的长期目标，为我生成一份每日总结和改进建议。
                         
                         【长期目标与指导原则】
                         {plans_context}
                         
                         【今日日程】
                         {event_text}
                         
                         【要求】
                         1. 总结今日完成情况，计算时间利用率（如果数据允许）。
                         2. 结合我的长期目标（特别是指导原则）进行点评。
                         3. 使用分隔符 "### 改进建议" 将总结和建议分开。
                         """
                         
                         response = st.session_state.brain.generate_text(prompt, system_instruction="你是一个高效的个人成长助手。请客观、犀利地分析日报。")
                         
                         # 4. Parse Response
                         if "### 改进建议" in response:
                             parts = response.split("### 改进建议")
                             summary_draft = parts[0].strip()
                             suggestion_draft = parts[1].strip()
                         else:
                             summary_draft = response
                             suggestion_draft = "请根据总结自行补充。"
                             
                         st.session_state['daily_summary_draft'] = summary_draft
                         st.session_state['daily_sugg_draft'] = suggestion_draft
                         st.rerun()
                    else:
                        st.error("日历适配器未初始化。")

        # Form
        with st.form("daily_log_form"):
            log_date = st.date_input("日期", value=datetime.date.today())
            
            # Update form fields if draft exists
            if 'daily_summary_draft' in st.session_state:
                st.session_state['log_summary'] = st.session_state.pop('daily_summary_draft')
            if 'daily_sugg_draft' in st.session_state:
                st.session_state['log_suggestions'] = st.session_state.pop('daily_sugg_draft')

            log_summary = st.text_area("今日总结", key="log_summary", height=200, placeholder="今天完成了什么？有什么收获？(点击上方按钮可 AI 生成)")
            log_suggestions = st.text_area("改进建议/明日计划", key="log_suggestions", height=150, placeholder="明天需要注意什么？")
            
            log_submit = st.form_submit_button("保存总结")
            
            if log_submit and log_summary:
                date_str = log_date.strftime("%Y-%m-%d")
                # When using key, get value from return valid or session state? Both work.
                res = mm.save_daily_log(date_str, log_summary, log_suggestions)
                st.success(res)
                time.sleep(1)
                st.rerun()
                
        st.divider()
        
        # 2. History
        st.subheader("📜 历史总结")
        logs_data = mm.get_logs_data()
        if logs_data:
            # Sort by date desc
            logs_data.sort(key=lambda x: x.get('date', ''), reverse=True)
            
            for log in logs_data:
                with st.expander(f"{log.get('date', 'Unknown Date')} 总结"):
                    st.markdown(f"**总结内容**: \n{log.get('summary', '')}")
                    if log.get('suggestions'):
                        st.markdown(f"**改进建议**: \n{log.get('suggestions', '')}")
                    st.caption(f"记录时间: {log.get('timestamp', '')}")
        else:
            st.info("暂无历史总结。")
    else:
        st.error("Memory Manager not initialized.")
