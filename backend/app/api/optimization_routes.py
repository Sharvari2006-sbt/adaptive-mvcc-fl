"""
Optimization Center Endpoints.
Interactive demonstration APIs for the 6 novelty DBMS features:
1. Adaptive Staleness Management
2. Priority Transaction Scheduling
3. Selective Rollback
4. Adaptive MVCC Garbage Collection
5. Transaction Conflict Prediction
6. Differential WAL Storage
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
from pydantic import BaseModel
import numpy as np

from app.db.session import get_db
from app.engine import coordinator

router = APIRouter(prefix="/optimization", tags=["Optimization Center"])

class StalenessConfigRequest(BaseModel):
    base_threshold: Optional[int] = None
    max_allowance: Optional[int] = None
    cosine_threshold: Optional[float] = None

class RollbackRequest(BaseModel):
    target_transaction_id: str
    reason: str

class ConflictPredictRequest(BaseModel):
    client_id: str
    staleness: int
    delta_norm: float = 0.15

# 1. Adaptive Staleness Management
@router.get("/staleness/config")
def get_staleness_config():
    """Returns current dynamic staleness threshold parameters."""
    return {
        "base_threshold": coordinator.staleness_mgr.base_threshold,
        "max_allowance": coordinator.staleness_mgr.max_allowance,
        "cosine_threshold": coordinator.staleness_mgr.cosine_threshold
    }

@router.post("/staleness/config")
def update_staleness_config(payload: StalenessConfigRequest):
    """Updates dynamic staleness threshold parameters from the dashboard."""
    coordinator.staleness_mgr.update_config(
        base_threshold=payload.base_threshold,
        max_allowance=payload.max_allowance,
        cosine_threshold=payload.cosine_threshold
    )
    return {
        "status": "CONFIG_UPDATED",
        "base_threshold": coordinator.staleness_mgr.base_threshold,
        "max_allowance": coordinator.staleness_mgr.max_allowance,
        "cosine_threshold": coordinator.staleness_mgr.cosine_threshold
    }

# 2. Priority Scheduling Queue
@router.get("/scheduler/queue")
def get_scheduler_status():
    """Returns real-time queue depth and priority scores with starvation metrics."""
    return {
        "queue_depth": coordinator.scheduler.size(),
        "queue": coordinator.scheduler.get_queue_status()
    }

# 3. Selective Rollback
@router.post("/rollback")
def execute_selective_rollback(payload: RollbackRequest, db: Session = Depends(get_db)):
    """Triggers deterministic model reconstruction excluding the specified poisoned transaction."""
    try:
        res = coordinator.rollback.rollback_transaction(
            target_transaction_id=payload.target_transaction_id,
            reason=payload.reason,
            db=db
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# 4. Adaptive Garbage Collection
@router.post("/gc/run")
def run_garbage_collection(keep_latest: int = 3, db: Session = Depends(get_db)):
    """Executes snapshot-aware garbage collection, preserving active client pins."""
    stats = coordinator.gc.run_garbage_collection(db, keep_latest_n=keep_latest)
    return stats

@router.get("/gc/stats")
def get_gc_stats():
    """Returns the most recent garbage collection statistics."""
    return coordinator.gc.get_last_stats()

# 5. Transaction Conflict Prediction
@router.post("/predict")
def test_conflict_prediction(payload: ConflictPredictRequest, db: Session = Depends(get_db)):
    """Tests advisory conflict prediction for arbitrary parameters."""
    dummy_delta = np.ones(321, dtype=np.float32) * (payload.delta_norm / np.sqrt(321))
    prediction = coordinator.predictor.predict_risk(
        txn_id=f"sim_pred_{payload.client_id}",
        client_id=payload.client_id,
        staleness=payload.staleness,
        client_delta=dummy_delta,
        current_queue_depth=coordinator.scheduler.size(),
        db=db
    )
    return prediction

# 6. Differential WAL Storage
@router.get("/differential/metrics")
def get_differential_metrics():
    """Returns comparative disk consumption: Full Model Snapshots vs Differential WAL deltas."""
    return coordinator.differential.get_comparison_metrics()
