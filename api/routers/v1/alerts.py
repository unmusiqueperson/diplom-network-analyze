import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

from fastapi import APIRouter, Depends, Request, Query
from slowapi import Limiter
from slowapi.util import get_remote_address
from clickhouse_driver import Client
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '../../../.env'))

from api.auth import get_current_user

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

def get_ch():
    return Client(
        host=os.getenv('CLICKHOUSE_HOST', 'localhost'),
        port=int(os.getenv('CLICKHOUSE_PORT', 9000)),
        user=os.getenv('CLICKHOUSE_USER', 'default'),
        password=os.getenv('CLICKHOUSE_PASSWORD', 'diplom123')
    )

@router.get("/alerts", summary="Последние аномалии")
@limiter.limit("30/minute")
async def get_alerts(
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    anomaly_type: str = Query(None),
    current_user: str = Depends(get_current_user)
):
    ch = get_ch()

    if anomaly_type:
        rows = ch.execute(f"""
            SELECT timestamp, src_ip, dst_ip, bytes,
                   anomaly_type, ensemble
            FROM anomaly_results
            WHERE anomaly_type = '{anomaly_type}'
            ORDER BY timestamp DESC
            LIMIT {limit}
        """)
    else:
        rows = ch.execute(f"""
            SELECT timestamp, src_ip, dst_ip, bytes,
                   anomaly_type, ensemble
            FROM anomaly_results
            ORDER BY timestamp DESC
            LIMIT {limit}
        """)

    return [
        {
            "timestamp": str(r[0]),
            "src_ip": r[1],
            "dst_ip": r[2],
            "bytes": r[3],
            "anomaly_type": r[4],
            "ensemble": r[5]
        }
        for r in rows
    ]

@router.get("/alerts/top-sources", summary="Топ источников аномалий")
@limiter.limit("30/minute")
async def get_top_sources(
    request: Request,
    limit: int = Query(10, ge=1, le=50),
    current_user: str = Depends(get_current_user)
):
    ch = get_ch()
    rows = ch.execute(f"""
        SELECT src_ip, count() AS anomalies, sum(bytes) AS total_bytes
        FROM anomaly_results
        GROUP BY src_ip
        ORDER BY anomalies DESC
        LIMIT {limit}
    """)
    return [
        {"src_ip": r[0], "anomalies": r[1], "total_bytes": r[2]}
        for r in rows
    ]
