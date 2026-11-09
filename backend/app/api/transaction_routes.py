"""
Transaction Management & Inspection Endpoints.
Allows monitoring and filtering all transaction lifecycles, states, and scheduling queue.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional

from app.db.session import get_db
from app.db.models import Transaction, Validation, ScheduleEntry, ConflictPrediction, WALRecord
from app.engine import coordinator

router = APIRouter(prefix="/transactions", tags=["Transactions"])

@router.get("", response_model=Dict[str, Any])
def list_transactions(
    status: Optional[str] = None,
    client_id: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """Retrieves paginated transactions with optional status and client filtering."""
    query = db.query(Transaction)
    if status and status.upper() != "ALL":
        query = query.filter(Transaction.status == status.upper())
    if client_id and client_id.upper() != "ALL":
        query = query.filter(Transaction.client_id == client_id)

    total_count = query.count()
    txns = query.order_by(Transaction.submitted_at.desc()).offset(offset).limit(limit).all()

    items = []
    for t in txns:
        val = db.query(Validation).filter(Validation.transaction_id == t.transaction_id).first()
        pred = db.query(ConflictPrediction).filter(ConflictPrediction.transaction_id == t.transaction_id).first()
        
        items.append({
            "transaction_id": t.transaction_id,
            "client_id": t.client_id,
            "base_version_id": t.base_version_id,
            "committed_version_id": t.committed_version_id,
            "status": t.status,
            "staleness": t.staleness,
            "priority_score": round(float(t.priority_score), 3),
            "submitted_at": t.submitted_at.isoformat() if t.submitted_at else None,
            "completed_at": t.completed_at.isoformat() if t.completed_at else None,
            "validation_result": val.validation_result if val else None,
            "conflict_score": round(float(val.conflict_score), 4) if val else None,
            "failure_reason": val.failure_reason if val else None,
            "predicted_risk_score": round(float(pred.risk_score), 4) if pred else None,
            "predicted_conflict": pred.predicted_conflict if pred else None
        })

    return {
        "total": total_count,
        "limit": limit,
        "offset": offset,
        "transactions": items
    }

@router.get("/queue", response_model=List[Dict[str, Any]])
def get_scheduler_queue():
    """Returns the live state of the priority transaction scheduler queue."""
    return coordinator.scheduler.get_queue_status()

@router.get("/{txn_id}", response_model=Dict[str, Any])
def get_transaction_detail(txn_id: str, db: Session = Depends(get_db)):
    """Retrieves end-to-end details, validations, and WAL entries for a specific transaction."""
    t = db.query(Transaction).filter(Transaction.transaction_id == txn_id).first()
    if not t:
        raise HTTPException(status_code=404, detail=f"Transaction {txn_id} not found.")

    val = db.query(Validation).filter(Validation.transaction_id == txn_id).first()
    pred = db.query(ConflictPrediction).filter(ConflictPrediction.transaction_id == txn_id).first()
    wal_recs = db.query(WALRecord).filter(WALRecord.transaction_id == txn_id).order_by(WALRecord.lsn.asc()).all()

    return {
        "transaction_id": t.transaction_id,
        "client_id": t.client_id,
        "base_version_id": t.base_version_id,
        "committed_version_id": t.committed_version_id,
        "status": t.status,
        "staleness": t.staleness,
        "priority_score": round(float(t.priority_score), 3),
        "submitted_at": t.submitted_at.isoformat() if t.submitted_at else None,
        "completed_at": t.completed_at.isoformat() if t.completed_at else None,
        "validation": {
            "validation_result": val.validation_result if val else None,
            "conflict_score": round(float(val.conflict_score), 4) if val else None,
            "failure_reason": val.failure_reason if val else None,
            "checked_at": val.checked_at.isoformat() if val and val.checked_at else None
        } if val else None,
        "conflict_prediction": {
            "risk_score": round(float(pred.risk_score), 4) if pred else None,
            "predicted_conflict": pred.predicted_conflict if pred else None,
            "evaluated_at": pred.evaluated_at.isoformat() if pred and pred.evaluated_at else None
        } if pred else None,
        "wal_records": [
            {
                "log_id": r.log_id,
                "lsn": r.lsn,
                "record_type": r.record_type,
                "checksum": r.checksum,
                "logged_at": r.logged_at.isoformat() if r.logged_at else None
            }
            for r in wal_recs
        ]
    }
