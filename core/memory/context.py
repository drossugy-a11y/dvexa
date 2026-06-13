"""会话上下文管理"""


class Context:
    """管理分析上下文"""
    
    def __init__(self):
        self.history = []
        self.current_regime = None
        self.current_strategy = None
    
    def add_result(self, result):
        """添加分析结果"""
        self.history.append(result)
    
    def get_recent(self, n=5):
        """获取最近N次结果"""
        return self.history[-n:]
