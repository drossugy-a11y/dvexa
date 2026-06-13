"""手动触发器"""


class Trigger:
    """手动触发分析任务"""
    
    def __init__(self, kernel):
        self.kernel = kernel
    
    def execute(self, config_path: str = None):
        """触发执行"""
        return self.kernel.run(config_path)
