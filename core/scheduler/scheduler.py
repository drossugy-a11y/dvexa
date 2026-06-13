"""定时调度器"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import logging
from config.settings import SCAN_HOUR, SCAN_MINUTE

logger = logging.getLogger(__name__)


class Scheduler:
    """定时调度器 - 每日定时扫描"""

    def __init__(self):
        self.scan_time = f"{SCAN_HOUR:02d}:{SCAN_MINUTE:02d}"
        self._scheduler = None

    def start(self):
        """启动调度器"""
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            self._scheduler = BackgroundScheduler()
            self._scheduler.add_job(self._run_scan, 'cron',
                                   hour=SCAN_HOUR, minute=SCAN_MINUTE,
                                   id='daily_scan')
            self._scheduler.start()
            logger.info(f"调度器已启动，每日 {self.scan_time} 执行扫描")
        except ImportError:
            logger.warning("APScheduler 未安装，定时功能不可用")

    def stop(self):
        """停止调度器"""
        if self._scheduler:
            self._scheduler.shutdown()
            logger.info("调度器已停止")

    def trigger_scan(self):
        """手动触发扫描"""
        self._run_scan()

    def _run_scan(self):
        """执行扫描 + 推送通知"""
        from core.engine.orchestrator import Orchestrator
        from integrations.notifier import Notifier

        logger.info("开始每日扫描...")
        orchestrator = Orchestrator()
        notifier = Notifier()

        try:
            result = orchestrator.run_daily_scan()
            notifier.send_scan_report(result)
            logger.info("每日扫描完成")
        except Exception as e:
            logger.error(f"扫描失败: {e}")
            notifier.send_alert("扫描失败", str(e))
