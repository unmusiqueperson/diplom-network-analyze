import os
import sys
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '../.env'))

from auth import get_current_user
from routers.v1 import stats, alerts, config
from cache import get_cache

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

# CORS: ограничен явными origins из env.
# Known limitation: WS-токен передаётся в URL-параметре (?token=...).
# Причина: браузерный WebSocket API не поддерживает кастомные заголовки.
# Митигация: токены короткоживущие (60 мин), передаются только по HTTPS в prod.
_raw_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8080")
ALLOWED_ORIGINS = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(stats.router,  prefix="/api/v1", tags=["Statistics"])
app.include_router(alerts.router, prefix="/api/v1", tags=["Alerts"])
app.include_router(config.router, prefix="/api/v1", tags=["Configuration"])

@app.get("/health", tags=["System"])
async def health_check():
    return {"status": "ok", "version": "1.0.0"}

@app.get("/ready", tags=["System"])
async def ready_check():
    try:
        cache = get_cache()
        cache.ping()
        return {"status": "ready", "redis": "ok"}
    except Exception:
        return {"status": "ready", "redis": "unavailable"}

from fastapi.security import OAuth2PasswordRequestForm
from auth import login, Token

@app.post("/api/v1/token", response_model=Token, tags=["Auth"])
async def get_token(form_data: OAuth2PasswordRequestForm = Depends()):
    return await login(form_data)
