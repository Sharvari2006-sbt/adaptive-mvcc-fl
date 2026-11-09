"""
MVCC Version Explorer Endpoints.
Allows visual exploration of the multi-version DAG lineage, parent-child links, and snapshot pins.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any, List

from app.db.session import get_db
from app.db.models import ModelVersion, ModelContribution
from app.engine import coordinator

router = APIRouter(prefix="/mvcc", tags=["MVCC Engine"])

@router.get("/versions", response_model=List[Dict[str, Any]])
def get_version_lineage():
    """Returns the complete directed acyclic graph (DAG) of model versions."""
    return coordinator.mvcc.get_lineage()

@router.get("/snapshots", response_model=Dict[str, str])
def get_active_snapshots():
    """Returns all active client snapshot pins: {client_id: version_id}."""
    return coordinator.mvcc.get_active_pins()

@router.get("/versions/{version_id}", response_model=Dict[str, Any])
def inspect_version(version_id: str, db: Session = Depends(get_db)):
    """Inspects detailed metadata and contributions associated with a specific model version."""
    v = db.query(ModelVersion).filter(ModelVersion.version_id == version_id).first()
    if not v:
        raise HTTPException(status_code=404, detail=f"Version {version_id} not found.")

    contributions = db.query(ModelContribution).filter(ModelContribution.model_version_id == version_id).all()

    try:
        weights = coordinator.mvcc.get_version_weights(version_id)
        weight_norm = float(np.linalg.norm(weights))
        weight_mean = float(np.mean(weights))
        weight_std = float(np.std(weights))
    except Exception:
        import numpy as np
        weight_norm = 0.0
        weight_mean = 0.0
        weight_std = 0.0

    return {
        "version_id": v.version_id,
        "parent_version_id": v.parent_version_id,
        "version_number": v.version_number,
        "checkpoint_path": v.checkpoint_path,
        "active_readers": v.active_readers,
        "loss": round(float(v.loss), 4),
        "accuracy": round(float(v.accuracy), 4),
        "created_at": v.created_at.isoformat() if v.created_at else None,
        "weights_summary": {
            "l2_norm": round(weight_norm, 4),
            "mean": round(weight_mean, 4),
            "std": round(weight_std, 4)
        },
        "contributions": [
            {
                "contribution_id": c.contribution_id,
                "transaction_id": c.transaction_id,
                "client_id": c.client_id,
                "weight_norm": round(float(c.weight_norm), 4),
                "is_active": c.is_active,
                "applied_at": c.applied_at.isoformat() if c.applied_at else None
            }
            for c in contributions
        ]
    }
