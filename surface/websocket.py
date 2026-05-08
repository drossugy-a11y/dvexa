"""Surface WebSocket — 实时系统状态推送

定时广播系统快照给所有已连接客户端。
事件类型: snapshot, evolution_event, governance_alert
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import WebSocket

from surface.snapshot_builder import SystemSnapshotBuilder

logger = logging.getLogger("dvexa.surface.ws")


class SurfaceWebSocket:
    """WebSocket 连接管理 + 定时广播。"""

    def __init__(self, snapshot_builder: SystemSnapshotBuilder, interval: float = 5.0):
        self._builder = snapshot_builder
        self._interval = interval
        self._connections: list[WebSocket] = []
        self._running = False

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.append(ws)
        logger.info(f"WebSocket connected ({len(self._connections)} total)")

    def disconnect(self, ws: WebSocket) -> None:
        self._connections.remove(ws)
        logger.info(f"WebSocket disconnected ({len(self._connections)} remaining)")

    async def broadcast(self, event_type: str, payload: dict[str, Any]) -> None:
        message = json.dumps({"type": event_type, "data": payload}, default=str)
        stale: list[WebSocket] = []
        for ws in self._connections:
            try:
                await ws.send_text(message)
            except Exception:
                stale.append(ws)
        for ws in stale:
            self.disconnect(ws)

    async def start_background_broadcast(self) -> None:
        """后台任务：定时广播快照。"""
        if self._running:
            return
        self._running = True
        logger.info(f"WebSocket broadcast started (interval={self._interval}s)")

        while self._running:
            await asyncio.sleep(self._interval)
            if not self._connections:
                continue
            try:
                snap = self._builder.build()
                await broadcast("snapshot", snap.to_dict())
            except Exception as e:
                logger.warning(f"Broadcast error: {e}")

    def stop(self) -> None:
        self._running = False
