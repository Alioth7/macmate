'''
Author: LiangSiyuan
Date: 2026-03-01 23:33:18
LastEditors: LiangSiyuan
LastEditTime: 2026-03-02 00:01:30
FilePath: /Agent/tool/calendar_adapter.py
'''
import datetime
import time
from core.tools import registry

# Soft-import EventKit so tool decorators always register
_eventkit_available = False
try:
    import EventKit
    from Foundation import NSDate, NSTimeZone
    _eventkit_available = True
except Exception:
    EventKit = None  # type: ignore
    NSDate = None    # type: ignore
    NSTimeZone = None  # type: ignore

try:
    from core.interfaces import CalendarController
except Exception:
    CalendarController = object  # type: ignore

class MacCalendarAdapter(CalendarController):
    def __init__(self):
        if not _eventkit_available:
            raise RuntimeError("EventKit/PyObjC not installed. Calendar features unavailable.")
        self.store = EventKit.EKEventStore.alloc().init()
        # 绑定工具实例到注册表
        registry.bind_instance(self)
        self._ensure_permission()

    @registry.register("add_calendar_event", "Create a new calendar event with automatic conflict detection. Args: title(str), start_time(str 'YYYY-MM-DD HH:MM'), end_time(str 'YYYY-MM-DD HH:MM'), notes(str). If there are conflicting events, this tool will NOT create the event and instead return the conflicts. You must then ask the user and call add_calendar_event_confirmed to force-create.")
    def add_event_tool(self, title: str, start_time: str, end_time: str, notes: str = "") -> str:
        """Create event with conflict check. Returns conflict warning if overlapping events exist."""
        try:
            fmt = "%Y-%m-%d %H:%M"
            if len(start_time.split(':')) == 3:
                start_time = start_time.rsplit(':', 1)[0]
            if len(end_time.split(':')) == 3:
                end_time = end_time.rsplit(':', 1)[0]
                
            dt_start = datetime.datetime.strptime(start_time, fmt)
            dt_end = datetime.datetime.strptime(end_time, fmt)

            # --- Time validation ---
            now = datetime.datetime.now()
            if dt_start < now - datetime.timedelta(minutes=5):
                return f"Error: Cannot schedule event in the past (Start time {start_time} is earlier than Now {now.strftime('%Y-%m-%d %H:%M')}). Please check the date."

            if dt_end <= dt_start:
                return f"Error: End time ({end_time}) must be later than Start time ({start_time})."

            # --- Conflict detection ---
            ns_start = self._datetime_to_nsdate(dt_start)
            ns_end = self._datetime_to_nsdate(dt_end)
            predicate = self.store.predicateForEventsWithStartDate_endDate_calendars_(
                ns_start, ns_end, None
            )
            existing = self.store.eventsMatchingPredicate_(predicate)
            
            if existing and len(existing) > 0:
                conflicts = []
                for ev in existing:
                    s_ts = ev.startDate().timeIntervalSince1970()
                    e_ts = ev.endDate().timeIntervalSince1970()
                    ev_start = datetime.datetime.fromtimestamp(s_ts).strftime('%H:%M')
                    ev_end = datetime.datetime.fromtimestamp(e_ts).strftime('%H:%M')
                    conflicts.append(f"  - '{ev.title()}' ({ev_start} ~ {ev_end})")
                
                conflict_list = "\n".join(conflicts)
                return (
                    f"CONFLICT_WARNING: The time slot {start_time} ~ {end_time} already has {len(existing)} event(s):\n"
                    f"{conflict_list}\n"
                    f"The event '{title}' was NOT created. Please ask the user whether to proceed. "
                    f"If the user confirms, call add_calendar_event_confirmed with the same arguments to force-create."
                )

            # No conflicts — create directly
            return self._do_create_event(title, dt_start, dt_end, notes, start_time)

        except Exception as e:
            return f"Exception during add_event_tool: {str(e)}"

    @registry.register("add_calendar_event_confirmed", "Force-create a calendar event (skip conflict check). Use ONLY after user has confirmed they want to create despite conflicts. Args: title(str), start_time(str 'YYYY-MM-DD HH:MM'), end_time(str 'YYYY-MM-DD HH:MM'), notes(str)")
    def add_event_confirmed_tool(self, title: str, start_time: str, end_time: str, notes: str = "") -> str:
        """Create event without conflict check — user already confirmed."""
        try:
            fmt = "%Y-%m-%d %H:%M"
            if len(start_time.split(':')) == 3:
                start_time = start_time.rsplit(':', 1)[0]
            if len(end_time.split(':')) == 3:
                end_time = end_time.rsplit(':', 1)[0]
            dt_start = datetime.datetime.strptime(start_time, fmt)
            dt_end = datetime.datetime.strptime(end_time, fmt)

            if dt_end <= dt_start:
                return f"Error: End time ({end_time}) must be later than Start time ({start_time})."

            return self._do_create_event(title, dt_start, dt_end, notes, start_time)
        except Exception as e:
            return f"Exception during add_event_confirmed_tool: {str(e)}"

    def _do_create_event(self, title: str, dt_start, dt_end, notes: str, start_time_str: str) -> str:
        """Internal: actually create the EKEvent."""
        event = EventKit.EKEvent.eventWithEventStore_(self.store)
        event.setTitle_(title)
        event.setStartDate_(self._datetime_to_nsdate(dt_start))
        event.setEndDate_(self._datetime_to_nsdate(dt_end))
        event.setNotes_(notes)
        
        ns_tz = NSTimeZone.timeZoneWithName_("Asia/Shanghai")
        event.setTimeZone_(ns_tz)
        
        default_calendar = self.store.defaultCalendarForNewEvents()
        if not default_calendar:
            return "Error: No default calendar found."
        event.setCalendar_(default_calendar)
        
        success, error = self.store.saveEvent_span_error_(event, 0, None)
        
        if success:
            return f"Success: Event '{title}' added on {start_time_str}."
        else:
            return f"Error: Failed to save event. {error}"

    @registry.register("delete_calendar_event", "Delete user's calendar event. Args: title(str), start_time(str 'YYYY-MM-DD HH:MM'), end_time(str 'YYYY-MM-DD HH:MM')")
    def delete_event_tool(self, title: str, start_time: str, end_time: str) -> str:
        try:
            fmt = "%Y-%m-%d %H:%M"
            if len(start_time.split(':')) == 3: start_time = start_time.rsplit(':', 1)[0]
            if len(end_time.split(':')) == 3: end_time = end_time.rsplit(':', 1)[0]

            start_dt = datetime.datetime.strptime(start_time, fmt)
            end_dt = datetime.datetime.strptime(end_time, fmt)

            # 1. 构造查找谓词
            safe_start = start_dt - datetime.timedelta(minutes=10)
            safe_end = end_dt + datetime.timedelta(minutes=10)

            ns_start = self._datetime_to_nsdate(safe_start)
            ns_end = self._datetime_to_nsdate(safe_end)
            
            predicate = self.store.predicateForEventsWithStartDate_endDate_calendars_(
                ns_start, ns_end, None
            )
            events = self.store.eventsMatchingPredicate_(predicate)
            
            if not events:
                return f"Info: To delete '{title}', but found 0 events in range {start_time} - {end_time}."
            
            deleted_count = 0
            
            # 使用倒序遍历，防止删除时索引变动影响（虽然这里是对象引用，安全起见）
            for event in events:
                evt_title = event.title()
                # 宽松匹配
                if title in evt_title or evt_title in title:
                    success, error = self.store.removeEvent_span_error_(event, 0, None)
                    if success:
                        deleted_count += 1
            
            if deleted_count > 0:
                # 某些时候需要显示提交
                # self.store.commit_(None)
                return f"Success: Deleted {deleted_count} event(s) matching '{title}'."
            else:
                found_titles = [e.title() for e in events]
                return f"Info: Found events {found_titles} but none matched '{title}'."

        except Exception as e:
            return f"Exception during delete_event_tool: {str(e)}"

    @registry.register("get_calendar_events", "Get calendar events (Read-Only). Args: start_time(str 'YYYY-MM-DD HH:MM'), end_time(str 'YYYY-MM-DD HH:MM')")
    def get_events_tool(self, start_time: str, end_time: str) -> str:
        """专门给 LLM 用的查询工具，返回易读的字符串"""
        try:
            fmt = "%Y-%m-%d %H:%M"
            # 容错秒
            if len(start_time.split(':')) == 3: start_time = start_time.rsplit(':', 1)[0]
            if len(end_time.split(':')) == 3: end_time = end_time.rsplit(':', 1)[0]
            
            dt_start = datetime.datetime.strptime(start_time, fmt)
            dt_end = datetime.datetime.strptime(end_time, fmt)
            
            ns_start = self._datetime_to_nsdate(dt_start)
            ns_end = self._datetime_to_nsdate(dt_end)
            
            predicate = self.store.predicateForEventsWithStartDate_endDate_calendars_(ns_start, ns_end, None)
            events = self.store.eventsMatchingPredicate_(predicate)
            
            if not events:
                return "Result: No events found."
            
            result_str = f"Found {len(events)} Events:\n"
            for e in events:
                s_ts = e.startDate().timeIntervalSince1970()
                e_ts = e.endDate().timeIntervalSince1970()
                
                # 转为本地时间字符串
                local_start = datetime.datetime.fromtimestamp(s_ts).strftime('%Y-%m-%d %H:%M')
                local_end = datetime.datetime.fromtimestamp(e_ts).strftime('%Y-%m-%d %H:%M')
                
                result_str += f"- Title: '{e.title()}', Start: '{local_start}', End: '{local_end}'\n"
            return result_str
        except Exception as e:
            return f"Error reading events: {e}"

    def _ensure_permission(self):
        """处理令人头疼的苹果 TCC 权限"""
        auth_status = EventKit.EKEventStore.authorizationStatusForEntityType_(EventKit.EKEntityTypeEvent)
        if auth_status != 3:
            print("⚠️ 正在向 MacOS 申请日历底层访问权限，请留意弹窗...")
            def auth_callback(granted, error):
                pass
            self.store.requestAccessToEntityType_completion_(EventKit.EKEntityTypeEvent, auth_callback)
            time.sleep(5) # 简易阻塞等待授权

    def _datetime_to_nsdate(self, dt: datetime.datetime) -> NSDate:
        return NSDate.dateWithTimeIntervalSince1970_(dt.timestamp())

    def add_event(self, title: str, start_dt: datetime.datetime, end_dt: datetime.datetime, notes: str = "") -> bool:
        try:
            event = EventKit.EKEvent.eventWithEventStore_(self.store)
            event.setTitle_(title)
            event.setStartDate_(self._datetime_to_nsdate(start_dt))
            event.setEndDate_(self._datetime_to_nsdate(end_dt))
            event.setNotes_(notes)
            
            # ====== 核心修复区：斩杀时区同步幽灵 ======
            # 强行生成一个苹果底层的上海时区对象，并绑定到事件上
            ns_tz = NSTimeZone.timeZoneWithName_("Asia/Shanghai")
            event.setTimeZone_(ns_tz)
            # ==========================================

            default_calendar = self.store.defaultCalendarForNewEvents()
            if not default_calendar:
                return False
                
            event.setCalendar_(default_calendar)
            success, error = self.store.saveEvent_span_error_(event, 0, None)
            return success
        except Exception as e:
            print(f"💣 Mac 底层执行异常: {e}")
            return False

    def delete_event(self, title: str, start_dt: datetime.datetime, end_dt: datetime.datetime) -> bool:
        """根据标题和时间范围删除日历事件"""
        try:
            # 1. 构造查找谓词(Predicate)
            # 扩大搜索范围：前后各宽限 5 分钟，防止 LLM生成的时间和实际存储时间有微小偏差
            safe_start = start_dt - datetime.timedelta(minutes=5)
            safe_end = end_dt + datetime.timedelta(minutes=5)

            ns_start = self._datetime_to_nsdate(safe_start)
            ns_end = self._datetime_to_nsdate(safe_end)
            
            # None 表示搜索所有日历
            predicate = self.store.predicateForEventsWithStartDate_endDate_calendars_(
                ns_start, ns_end, None
            )
            
            # 2. 获取匹配的时间范围内所有事件
            events = self.store.eventsMatchingPredicate_(predicate)
            
            if not events:
                print(f"⚠️ 在指定时间段未找到名为 '{title}' 的事件")
                return False

            # 3. 遍历筛选标题完全匹配的项 (支持模糊匹配)
            target_event = None
            found_titles = []
            for event in events:
                evt_title = event.title()
                found_titles.append(evt_title)
                # 宽松匹配：只要包含或者被包含即可 (因为 LLM 记忆的标题可能不全)
                if title in evt_title or evt_title in title:
                    target_event = event
                    break 
            
            if not target_event:
                print(f"⚠️ 时间段内有事件，但标题不匹配。")
                print(f"   目标: {title}")
                print(f"   找到: {found_titles}")
                return False
                
            # 4. 执行删除操作 (span=0 表示只删除当前事件)
            # 注意：removeEvent_span_error_ 需要传入 error 指针的占位符，但在 Python 中通常返回 (bool, error)
            success, error = self.store.removeEvent_span_error_(target_event, 0, None)
            
            if not success:
                print(f"🤯 删除操作被系统拒绝: {error}")
                # 尝试提交变更
                self.store.commit_(None)
                return False
            
            # 显式提交变更 (某些系统版本需要)
            # self.store.commit_(None) 
            # save/remove 自动 commit，但如果大量操作可能需要手动。这里加上保险。
            
            print(f"✅ 已从日历移除: {target_event.title()}")
            return True

        except Exception as e:
            print(f"💣 删除过程发生异常: {e}")
            return False

    def get_events(self, start_dt: datetime.datetime, end_dt: datetime.datetime) -> list:
        """获取指定时间段内的所有日程"""
        try:
            ns_start = self._datetime_to_nsdate(start_dt)
            ns_end = self._datetime_to_nsdate(end_dt)
            
            predicate = self.store.predicateForEventsWithStartDate_endDate_calendars_(
                ns_start, ns_end, None
            )
            
            events = self.store.eventsMatchingPredicate_(predicate)
            
            result = []
            if events:
                for event in events:
                    # 只有日历事件(EKEvent)才有 title, startDate, endDate 属性
                    # EKEntityTypeEvent = 0
                    
                    # 转换 NSDate -> datetime (UTC)
                    # 简单起见，我们直接构造一个易读的字符串给 LLM，带上时区偏移更好，或者直接给本地时间
                    # 这里偷懒直接用 str(event.startDate()) 通常是 UTC
                    # 为了让 LLM 更准，我们尝试转成本地时间字符串
                    
                    # Python datetime fix
                    s_ts = event.startDate().timeIntervalSince1970()
                    e_ts = event.endDate().timeIntervalSince1970()
                    
                    local_start = datetime.datetime.fromtimestamp(s_ts).strftime('%Y-%m-%d %H:%M:%S')
                    local_end = datetime.datetime.fromtimestamp(e_ts).strftime('%Y-%m-%d %H:%M:%S')

                    result.append({
                        "title": event.title(),
                        "start": local_start, 
                        "end": local_end,
                        "notes": event.notes()
                    })
            
            return result
        except Exception as e:
            print(f"💣 读取日历异常: {e}")
            return []

    def get_detailed_events(self, start_time: str, end_time: str) -> list:
        """
        返回结构化日历数据 (List of Dict)，供前端渲染图表。
        格式: [{'Task': 'Meeting', 'Start': dt, 'Finish': dt, 'Resource': '...'}, ...]
        """
        try:
            fmt = "%Y-%m-%d %H:%M"
            # 容错秒
            if len(start_time.split(':')) == 3: start_time = start_time.rsplit(':', 1)[0]
            if len(end_time.split(':')) == 3: end_time = end_time.rsplit(':', 1)[0]
            
            dt_start = datetime.datetime.strptime(start_time, fmt)
            dt_end = datetime.datetime.strptime(end_time, fmt)
            
            ns_start = self._datetime_to_nsdate(dt_start)
            ns_end = self._datetime_to_nsdate(dt_end)
            
            predicate = self.store.predicateForEventsWithStartDate_endDate_calendars_(ns_start, ns_end, None)
            events = self.store.eventsMatchingPredicate_(predicate)
            
            result = []
            if not events: return []
            
            for e in events:
                s_ts = e.startDate().timeIntervalSince1970()
                e_ts = e.endDate().timeIntervalSince1970()
                
                start_dt = datetime.datetime.fromtimestamp(s_ts)
                end_dt = datetime.datetime.fromtimestamp(e_ts)
                
                duration_hours = (end_dt - start_dt).total_seconds() / 3600
                
                result.append({
                    "Task": e.title(),
                    "Start": start_dt.strftime("%Y-%m-%d %H:%M"),
                    "Finish": end_dt.strftime("%Y-%m-%d %H:%M"),
                    "Resource": "Calendar",  # 用于 Gantt 颜色分组
                    "Duration": f"{duration_hours:.1f}h"
                })
            return result
        except Exception as e:
            print(f"Error fetching detailed events: {e}")
            return []

    def update_event_time(self, title: str, old_start_str: str, new_start_str: str, new_end_str: str) -> str:
        """
        修改日程时间。
        由于 EventKit 没有直接 ID 查询 (跨 Session 可能失效)，我们用 Title + Old Start 定位。
        """
        try:
            fmt = "%Y-%m-%d %H:%M"
            
            # 容错秒
            if len(old_start_str.split(':')) == 3: old_start_str = old_start_str.rsplit(':', 1)[0]
            if len(new_start_str.split(':')) == 3: new_start_str = new_start_str.rsplit(':', 1)[0]
            if len(new_end_str.split(':')) == 3: new_end_str = new_end_str.rsplit(':', 1)[0]

            # 1. 解析时间
            old_start_dt = datetime.datetime.strptime(old_start_str, fmt)
            new_start_dt = datetime.datetime.strptime(new_start_str, fmt)
            new_end_dt = datetime.datetime.strptime(new_end_str, fmt)

            # 2. 查找原事件 (范围放宽一点避免秒级误差)
            # 在 old_start 前后几小时找
            search_start = old_start_dt - datetime.timedelta(hours=24)
            search_end = old_start_dt + datetime.timedelta(hours=24) 

            ns_start = self._datetime_to_nsdate(search_start)
            ns_end = self._datetime_to_nsdate(search_end)
            
            predicate = self.store.predicateForEventsWithStartDate_endDate_calendars_(ns_start, ns_end, None)
            events = self.store.eventsMatchingPredicate_(predicate)
            
            target_event = None
            if events:
                for e in events:
                    if e.title() == title:
                        # 进一步确认开始时间接近 (误差小于 5 分钟)
                        e_start_ts = e.startDate().timeIntervalSince1970()
                        e_start = datetime.datetime.fromtimestamp(e_start_ts)
                        
                        # 比较时要把 old_start_dt 视作本地时间
                        diff = abs((e_start - old_start_dt).total_seconds())
                        if diff < 300: 
                            target_event = e
                            break
            
            if not target_event:
                return f"Error: Could not find event '{title}' around {old_start_str}"
            
            # 3. 修改并保存
            target_event.setStartDate_(self._datetime_to_nsdate(new_start_dt))
            target_event.setEndDate_(self._datetime_to_nsdate(new_end_dt))
            
            success, error = self.store.saveEvent_span_error_(target_event, 0, None)
            
            if success:
                return f"Success: Updated '{title}' to {new_start_str} - {new_end_str}"
            else:
                return f"Error saving event: {error}"

        except Exception as e:
            return f"Exception updating event: {e}"

