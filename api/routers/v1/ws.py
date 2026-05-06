import os
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from jose import JWTError, jwt

from ws_manager import manager

router = APIRouter()

SECRET_KEY = os.getenv("API_SECRET_KEY", "diplom_secret_key_2026")
ALGORITHM  = "HS256"


def _validate_token(token: str) -> bool:
    """Возвращает True если токен валиден."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub") is not None
    except JWTError:
        return False


@router.websocket("/ws/alerts")
async def ws_alerts(
    websocket: WebSocket,
    token: str = Query(default=""),
):
    if not _validate_token(token):
        await websocket.close(code=4001)
        return

    await manager.connect(websocket)
    try:
        # Держим соединение: ждём сообщений от клиента (ping или close)
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        manager.disconnect(websocket)
