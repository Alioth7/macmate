'''
Author: LiangSiyuan
Date: 2026-03-01 23:33:47
LastEditors: LiangSiyuan
LastEditTime: 2026-03-01 23:34:00
FilePath: /Agent/core/interface.py
'''
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict

class CalendarController(ABC):
    """日历控制器的抽象基类，屏蔽底层操作系统的差异"""
    
    @abstractmethod
    def add_event(self, title: str, start_dt: datetime, end_dt: datetime, notes: str = "") -> bool:
        """向系统日历静默写入日程"""
        pass
        
    @abstractmethod
    def delete_event(self, title: str, start_dt: datetime, end_dt: datetime) -> bool:
        """从系统日历删除日程"""
        pass

    @abstractmethod
    def get_events(self, start_dt: datetime, end_dt: datetime) -> List[Dict]:
        """获取指定时间段内的所有日程"""
        pass


        
    # 未来可以继续扩展：
    # @abstractmethod
    # def get_free_slots(self, date: datetime) -> List[Dict]:
    #     pass