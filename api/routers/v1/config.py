import os
import sys
import yaml
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

from fastapi import APIRouter, Depends, Request, HTTPException
from slowapi import Limiter
from slowapi.util import get_remote_address
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '../../../.env'))

from api.auth import get_current_user

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), '../../../config/algorithms.yml')

class ZScoreConfig(BaseModel):
    threshold: float
    window_size: int

class EnsembleConfig(BaseModel):
    min_votes: int
    use_weights: bool

@router.get("/config", summary="Получить текущие параметры алгоритмов")
@limiter.limit("30/minute")
async def get_config(request: Request, current_user: str = Depends(get_current_user)):
    with open(CONFIG_PATH, 'r') as f:
        return yaml.safe_load(f)

@router.post("/config/zscore", summary="Обновить параметры Z-score")
@limiter.limit("10/minute")
async def update_zscore(
    request: Request,
    cfg: ZScoreConfig,
    current_user: str = Depends(get_current_user)
):
    with open(CONFIG_PATH, 'r') as f:
        config = yaml.safe_load(f)

    config['zscore']['threshold'] = cfg.threshold
    config['zscore']['window_size'] = cfg.window_size

    with open(CONFIG_PATH, 'w') as f:
        yaml.dump(config, f)

    return {"status": "updated", "zscore": config['zscore']}

@router.post("/config/ensemble", summary="Обновить параметры Ensemble")
@limiter.limit("10/minute")
async def update_ensemble(
    request: Request,
    cfg: EnsembleConfig,
    current_user: str = Depends(get_current_user)
):
    with open(CONFIG_PATH, 'r') as f:
        config = yaml.safe_load(f)

    config['ensemble']['min_votes'] = cfg.min_votes
    config['ensemble']['use_weights'] = cfg.use_weights

    with open(CONFIG_PATH, 'w') as f:
        yaml.dump(config, f)

    return {"status": "updated", "ensemble": config['ensemble']}

