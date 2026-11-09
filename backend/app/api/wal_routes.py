"""
WAL and Crash Recovery Endpoints.
Provides live WAL record browsing, CRC32 integrity verification,
simulated crash triggers, and ARIES restart recovery.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Dict, Any, List

from app.db.session import get_db
from app.engine import coordinator

router = APIRouter(prefix="/wal", tags=["WAL & Recovery"])

@router.get("/records", response_model=Dict[str, Any])
def get_wal_records(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0)
):
    """Browses append-only WAL records directly from the persistent disk file."""
    all_records = coordinator.wal.read_all_records()
    total = len(all_records)
    # Return latest records first
    sliced = list(reversed(all_records))[offset : offset + limit]

    sanitized = []
    for r in sliced:
        sanitized.append({
            "log_id": r.get("log_id"),
            "lsn": r.get("lsn"),
            "record_type": r.get("record_type"),
            "transaction_id": r.get("transaction_id"),
            "client_id": r.get("client_id"),
            "base_version": r.get("base_version"),
            "data_reference": r.get("data_reference"),
            "checksum": r.get("checksum"),
            "timestamp": r.get("timestamp"),
            "has_delta": r.get("sparse_delta") is not None
        })

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "records": sanitized
    }

@router.get("/integrity", response_model=Dict[str, Any])
def verify_wal_integrity():
    """Scans all WAL records and verifies CRC32 checksums to detect file tampering or torn writes."""
    is_valid, corrupted_lsns = coordinator.wal.verify_integrity()
    return {
        "is_valid": is_valid,
        "total_records_checked": len(coordinator.wal.read_all_records()),
        "corrupted_lsns": corrupted_lsns,
        "status": "HEALTHY" if is_valid else "CORRUPTION_DETECTED"
    }

@router.post("/simulate-crash")
def simulate_server_crash():
    """Simulates an abrupt coordinator power outage or server crash."""
    coordinator.recovery.simulate_crash()
    return {
        "is_crashed": True,
        "message": "Server crash simulated successfully. Coordinator is offline until Restart and Recover is triggered."
    }

@router.post("/restart-recover")
def restart_and_recover(db: Session = Depends(get_db)):
    """Executes ARIES recovery: scans checkpoint, redoes committed updates, aborts incomplete transactions."""
    recovery_stats = coordinator.recovery.restart_and_recover(db)
    return recovery_stats

@router.get("/recovery-stats")
def get_recovery_status():
    """Returns the results of the most recent crash recovery operation."""
    return {
        "is_crashed": coordinator.recovery.is_crashed,
        "last_recovery": coordinator.recovery.get_last_recovery_stats()
    }

@router.post("/checkpoint")
def trigger_checkpoint(db: Session = Depends(get_db)):
    """Manually creates a consistent checkpoint snapshot of the global model."""
    weights = coordinator.mvcc.get_version_weights(coordinator.mvcc.current_version_id)
    rec = coordinator.wal.create_checkpoint(coordinator.mvcc.current_version_id, weights, db=db)
    return {
        "checkpoint_lsn": rec["lsn"],
        "checkpoint_path": rec["data_reference"],
        "version_id": rec["base_version"]
    }
