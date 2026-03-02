import inspect
from functools import wraps
from typing import Callable, Dict, Any, Optional

class ToolRegistry:
    def __init__(self):
        self.tools: Dict[str, Callable] = {}
        self.tool_descriptions: str = ""
        # 存储绑定的实例，key 是函数对象，value 是实例
        self.bound_instances = {}

    def register(self, name: str, description: str):
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            
            # 存储原始未绑定的函数
            self.tools[name] = func
            
            # 自动生成工具描述，供 LLM 阅读
            sig = inspect.signature(func)
            params = [f"{k}" for k in sig.parameters.keys() if k != 'self']
            self.tool_descriptions += f"- {name}({', '.join(params)}): {description}\n"
            return wrapper
        return decorator

    def bind_instance(self, instance):
        """将实例绑定到其下的工具方法上"""
        if not instance: return

        cls_name = instance.__class__.__name__
        for name, func in self.tools.items():
            # 兼容装饰器 wrapper 的情况，尝试获取原始函数
            real_func = func  
            while hasattr(real_func, '__wrapped__'):
                real_func = real_func.__wrapped__
                
            if hasattr(real_func, '__qualname__') and f"{cls_name}." in real_func.__qualname__:
                self.bound_instances[name] = instance

    def get_tool(self, name: str):
        tool = self.tools.get(name)
        if not tool: return None
        
        instance = self.bound_instances.get(name)
        
        if instance:
            # 返回一个闭包，手动传入 self
            def bound_wrapper(*args, **kwargs):
                return tool(instance, *args, **kwargs)
            return bound_wrapper
        
        return tool

    def get_descriptions(self):
        return self.tool_descriptions

# 全局工具注册表
registry = ToolRegistry()
