"""通知推送 - Telegram / 企业微信 / 控制台"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import json
import logging
import requests
from datetime import datetime
from config.settings import (
    NOTIFY_CHANNEL, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, WECHAT_WEBHOOK_URL
)

logger = logging.getLogger(__name__)


class Notifier:
    """通知推送"""

    def __init__(self, channel: str = None):
        self.channel = channel or NOTIFY_CHANNEL

    def send(self, message: str) -> bool:
        """发送消息"""
        if self.channel == 'telegram':
            return self._send_telegram(message)
        elif self.channel == 'wechat':
            return self._send_wechat(message)
        else:
            return self._send_console(message)

    def send_scan_report(self, scan_result: dict) -> bool:
        """发送扫描报告"""
        msg = self._format_report(scan_result)
        return self.send(msg)

    def send_alert(self, title: str, body: str) -> bool:
        """发送告警"""
        msg = f"🚨 {title}\n{body}"
        return self.send(msg)

    def _format_report(self, result: dict) -> str:
        """格式化扫描报告"""
        regime = result.get('regime', 'unknown')
        strategy = result.get('strategy_name', '')
        candidates = result.get('candidates', [])

        emoji_map = {'bull': '📈', 'bear': '📉', 'shock': '📊'}
        emoji = emoji_map.get(regime, '📊')

        lines = [
            f"📊 DVexa 每日选股报告 [{datetime.now().strftime('%Y-%m-%d')}]",
            "",
            f"{emoji} 市场状态: {regime}",
            f"📋 策略: {strategy}",
            "",
            f"🏆 Top {len(candidates)} 推荐:",
        ]

        for i, d in enumerate(candidates, 1):
            name = d.get('name', d.get('ticker', ''))
            ticker = d.get('ticker', '')
            action = d.get('action', '')
            pct = d.get('target_pct', 0) * 100
            reason = d.get('reason', '')

            lines.append(f"{i}. {name}({ticker}) | AI: {action} | 仓位:{pct:.0f}%")
            if reason:
                lines.append(f"   💡 {reason}")

            entry = d.get('entry_price', 0)
            stop = d.get('stop_loss', 0)
            tp = d.get('take_profit', 0)
            if entry:
                lines.append(f"   🎯 入场:{entry} 止损:{stop} 止盈:{tp}")

        return '\n'.join(lines)

    def _send_telegram(self, message: str) -> bool:
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            logger.warning("Telegram 配置缺失")
            return False
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            resp = requests.post(url, json={
                'chat_id': TELEGRAM_CHAT_ID,
                'text': message,
                'parse_mode': 'HTML',
            }, timeout=10)
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"Telegram 发送失败: {e}")
            return False

    def _send_wechat(self, message: str) -> bool:
        if not WECHAT_WEBHOOK_URL:
            logger.warning("企业微信 webhook 配置缺失")
            return False
        try:
            resp = requests.post(WECHAT_WEBHOOK_URL, json={
                'msgtype': 'text',
                'text': {'content': message},
            }, timeout=10)
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"企业微信发送失败: {e}")
            return False

    def _send_console(self, message: str) -> bool:
        print("\n" + "=" * 50)
        print(message)
        print("=" * 50 + "\n")
        return True
