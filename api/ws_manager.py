import json
import logging
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self._connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.append(ws)
        logger.info(f"WS client connected. Total: {len(self._connections)}")

    def disconnect(self, ws: WebSocket) -> None:
        self._connections = [c for c in self._connections if c is not ws]
        logger.info(f"WS client disconnected. Total: {len(self._connections)}")

    async def broadcast(self, data: dict) -> None:
        if not self._connections:
            return

        # default=str покрывает datetime и прочие несериализуемые типы
        message = json.dumps(data, default=str)

        dead: list[WebSocket] = []
        for ws in self._connections:
            try:
                await ws.send_text(message)
            except Exception as e:
                logger.warning(f"WS send failed: {e}")
                dead.append(ws)

        for ws in dead:
            self.disconnect(ws)

    @property
    def count(self) -> int:
        return len(self._connections)


# Синглтон — импортируется в ws.py и main.py
manager = ConnectionManager()
