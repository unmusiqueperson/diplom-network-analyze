import json
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

from fastapi import APIRouter, Depends, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from clickhouse_driver import Client
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '../../../.env'))

from api.auth import get_current_user
from api.cache import cache_get, cache_set

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

def get_ch():
    return Client(
        host=os.getenv('CLICKHOUSE_HOST', 'localhost'),
        port=int(os.getenv('CLICKHOUSE_PORT', 9000)),
        user=os.getenv('CLICKHOUSE_USER', 'default'),
        password=os.getenv('CLICKHOUSE_PASSWORD', 'diplom123')
    )

@router.get("/stats", summary="Общая статистика событий")
@limiter.limit("30/minute")
async def get_stats(request: Request, current_user: str = Depends(get_current_user)):
    cached = cache_get("stats")
    if cached:
        return json.loads(cached)

    ch = get_ch()
    total = ch.execute("SELECT count() FROM network_events")[0][0]
    anomalies = ch.execute("SELECT sum(is_anomaly) FROM network_events")[0][0]
    by_type = ch.execute(
        "SELECT anomaly_type, count() FROM anomaly_results GROUP BY anomaly_type"
    )

    result = {
        "total_events": total,
        "total_anomalies": anomalies,
        "anomaly_rate": round(anomalies / total * 100, 2) if total > 0 else 0,
        "by_type": {row[0]: row[1] for row in by_type}
    }

    cache_set("stats", json.dumps(result), ttl=30)
    return result

@router.get("/stats/timeseries", summary="События по времени")
@limiter.limit("30/minute")
async def get_timeseries(request: Request, current_user: str = Depends(get_current_user)):
    ch = get_ch()
    rows = ch.execute("""
        SELECT
            toStartOfMinute(timestamp) AS minute,
            count() AS events,
            sum(is_anomaly) AS anomalies
        FROM network_events
        WHERE timestamp >= now() - INTERVAL 1 HOUR
        GROUP BY minute
        ORDER BY minute
    """)
    return [{"time": str(r[0]), "events": r[1], "anomalies": r[2]} for r in rows]
