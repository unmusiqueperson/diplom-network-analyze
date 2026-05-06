import os
import asyncio
import logging
from datetime import datetime, timezone

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '../.env'))

from auth import get_current_user
from routers.v1 import stats, alerts, config, ws as ws_router
from cache import get_cache
from ws_manager import manager

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="Network Events Analyzer API",
    description="API для управления модулем анализа сетевых событий интернет-провайдера",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(stats.router,      prefix="/api/v1", tags=["Statistics"])
app.include_router(alerts.router,     prefix="/api/v1", tags=["Alerts"])
app.include_router(config.router,     prefix="/api/v1", tags=["Configuration"])
app.include_router(ws_router.router,  tags=["WebSocket"])


# ── ClickHouse poller ────────────────────────────────────────────
# Опрашивает anomaly_results каждые 3 сек, новые записи → broadcast

def _fetch_new_rows(cursor: datetime) -> tuple[list[dict], datetime]:
    """Синхронный запрос к ClickHouse (выполняется в потоке)."""
    from clickhouse_driver import Client

    ch = Client(
        host=os.getenv("CLICKHOUSE_HOST", "localhost"),
        port=int(os.getenv("CLICKHOUSE_PORT", 9000)),
        user=os.getenv("CLICKHOUSE_USER", "default"),
        password=os.getenv("CLICKHOUSE_PASSWORD", "diplom123"),
    )

    rows = ch.execute("""
        SELECT timestamp, src_ip, dst_ip, bytes, anomaly_type, ensemble
        FROM anomaly_results
        WHERE timestamp > %(cursor)s
        ORDER BY timestamp ASC
        LIMIT 100
    """, {"cursor": cursor})

    new_cursor = cursor
    result = []
    for r in rows:
        ts = r[0]  # datetime из ClickHouse
        result.append({
            "timestamp":    ts.strftime("%Y-%m-%d %H:%M:%S"),
            "src_ip":       r[1],
            "dst_ip":       r[2],
            "bytes":        r[3],
            "anomaly_type": r[4],
            "ensemble":     r[5],
        })
        if ts > new_cursor:
            new_cursor = ts

    return result, new_cursor


async def _anomaly_poller():
    """Фоновая задача: опрашивает ClickHouse, бродкастит новые аномалии."""
    # Курсор — текущий момент, чтобы не флудить историческими данными
    cursor = datetime.now(tz=timezone.utc).replace(tzinfo=None)
    logger.info("WS poller started.")

    while True:
        await asyncio.sleep(3)

        if manager.count == 0:
            continue  # нет подключённых клиентов — не тратим ресурсы

        try:
            rows, cursor = await asyncio.to_thread(_fetch_new_rows, cursor)
            for row in rows:
                await manager.broadcast(row)
        except Exception as e:
            logger.error(f"WS poller error: {e}")


@app.on_event("startup")
async def startup():
    asyncio.create_task(_anomaly_poller())


# ── Health / Ready ───────────────────────────────────────────────

@app.get("/health", tags=["System"])
async def health_check():
    return {"status": "ok", "version": "1.0.0", "ws_clients": manager.count}


@app.get("/ready", tags=["System"])
async def ready_check():
    try:
        cache = get_cache()
        cache.ping()
        return {"status": "ready", "redis": "ok"}
    except Exception:
        return {"status": "ready", "redis": "unavailable"}


# ── Auth ─────────────────────────────────────────────────────────

from fastapi.security import OAuth2PasswordRequestForm
from fastapi import Depends
from auth import login, Token

@app.post("/api/v1/token", response_model=Token, tags=["Auth"])
async def get_token(form_data: OAuth2PasswordRequestForm = Depends()):
    return await login(form_data)
