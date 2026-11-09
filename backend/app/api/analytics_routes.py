"""
Reports and Analytics Endpoints.
Aggregates performance metrics, convergence curves, commit/abort ratios,
and provides CSV downloads for academic evaluation.
"""
from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Dict, Any, List
import io
import csv
import time
from pathlib import Path
import numpy as np

from app.db.session import get_db
from app.db.models import Transaction, ModelVersion, Client, WALRecord, ModelContribution
from app.engine import coordinator, simulator
from app.fl.aggregation import apply_weight_delta

router = APIRouter(prefix="/analytics", tags=["Analytics"])

@router.get("/overview", response_model=Dict[str, Any])
def get_dashboard_overview(db: Session = Depends(get_db)):
    """Computes high-level KPIs for Page 1 of the monitoring dashboard."""
    total_txns = db.query(Transaction).count()
    committed_txns = db.query(Transaction).filter(Transaction.status == "COMMITTED").count()
    aborted_txns = db.query(Transaction).filter(Transaction.status == "ABORTED").count()
    pending_txns = db.query(Transaction).filter(Transaction.status.in_(["PENDING", "VALIDATING"])).count()

    active_clients = sum(1 for c in simulator.clients.values() if c.status == "ACTIVE")
    current_vid = coordinator.mvcc.current_version_id
    current_vnum = coordinator.mvcc.current_version_number

    # Latest model version metrics
    latest_v = db.query(ModelVersion).filter(ModelVersion.version_id == current_vid).first()
    loss = round(float(latest_v.loss), 4) if latest_v else 0.0
    accuracy = round(float(latest_v.accuracy), 4) if latest_v else 0.0

    # Storage metrics
    diff_metrics = coordinator.differential.get_comparison_metrics()

    # Commit rate
    commit_rate = round((committed_txns / total_txns * 100.0), 1) if total_txns > 0 else 100.0

    return {
        "active_clients": active_clients,
        "total_clients": len(simulator.clients),
        "current_version_id": current_vid,
        "current_version_number": current_vnum,
        "model_loss": loss,
        "model_accuracy": accuracy,
        "total_transactions": total_txns,
        "committed_transactions": committed_txns,
        "aborted_transactions": aborted_txns,
        "pending_transactions": pending_txns,
        "commit_rate_percent": commit_rate,
        "storage_consumed_bytes": diff_metrics["differential_logging_bytes"],
        "storage_saved_mb": diff_metrics["storage_saved_mb"],
        "storage_reduction_percent": diff_metrics["storage_reduction_percent"],
        "is_server_crashed": coordinator.recovery.is_crashed
    }

@router.get("/history", response_model=Dict[str, Any])
def get_historical_timeseries(db: Session = Depends(get_db)):
    """Returns chronologically ordered data for Recharts convergence and throughput graphs."""
    versions = db.query(ModelVersion).order_by(ModelVersion.version_number.asc()).all()
    accuracy_series = [
        {
            "version": v.version_id,
            "version_number": v.version_number,
            "accuracy": round(float(v.accuracy) * 100.0, 2),
            "loss": round(float(v.loss), 4),
            "active_readers": v.active_readers
        }
        for v in versions
    ]

    # Client contribution breakdown
    client_stats = simulator.get_all_client_stats()

    return {
        "accuracy_loss_series": accuracy_series,
        "client_stats": client_stats
    }


@router.get("/baseline-comparison", response_model=Dict[str, Any])
def compare_with_last_writer_wins(db: Session = Depends(get_db)):
    """Replays recorded updates using a naive overwrite policy for comparison.

    Each accepted delta is applied to its original client snapshot and replaces
    the previous candidate model. This is a deterministic algorithm comparison,
    not a claim about end-to-end training throughput or production performance.
    """
    contributions = (
        db.query(ModelContribution)
        .filter(ModelContribution.is_active.is_(True))
        .order_by(ModelContribution.applied_at.asc())
        .all()
    )
    started = time.perf_counter()
    baseline_weights = None
    replayed = 0
    skipped = 0

    for contribution in contributions:
        txn = db.query(Transaction).filter_by(transaction_id=contribution.transaction_id).first()
        delta_path = Path(contribution.update_reference)
        if not txn or not delta_path.exists():
            skipped += 1
            continue
        try:
            snapshot_weights = coordinator.mvcc.get_version_weights(txn.base_version_id)
            delta = np.load(delta_path).astype(np.float32)
        except (ValueError, FileNotFoundError, OSError):
            skipped += 1
            continue
        if snapshot_weights.shape != delta.shape:
            skipped += 1
            continue
        # Last-writer-wins drops prior state whenever a later client submits an
        # update based on an older snapshot instead of rebasing on the head.
        baseline_weights = apply_weight_delta(snapshot_weights, delta, scaling_factor=1.0)
        replayed += 1

    replay_ms = (time.perf_counter() - started) * 1000.0
    if baseline_weights is None:
        return {
            "status": "NO_REPLAYABLE_CONTRIBUTIONS",
            "replayed_contributions": 0,
            "skipped_contributions": skipped,
            "protocol": "Original-snapshot last-writer-wins replay; excludes local training and database I/O.",
        }

    engine_weights = coordinator.mvcc.get_version_weights(coordinator.mvcc.current_version_id)
    baseline_loss, baseline_accuracy = coordinator._evaluate_weights(baseline_weights)
    engine_loss, engine_accuracy = coordinator._evaluate_weights(engine_weights)
    return {
        "status": "COMPARISON_READY",
        "replayed_contributions": replayed,
        "skipped_contributions": skipped,
        "baseline_policy": "Original-snapshot last-writer-wins",
        "engine_policy": "Validated MVCC commit with head rebasing",
        "baseline_accuracy": round(float(baseline_accuracy), 6),
        "engine_accuracy": round(float(engine_accuracy), 6),
        "baseline_loss": round(float(baseline_loss), 6),
        "engine_loss": round(float(engine_loss), 6),
        "weight_difference_l2": round(float(np.linalg.norm(engine_weights - baseline_weights)), 6),
        "baseline_replay_ms": round(replay_ms, 3),
        "protocol": "Deterministic replay of recorded deltas against their original snapshots; excludes local training and database I/O, and is not an end-to-end performance benchmark.",
    }

@router.get("/export-csv")
def export_experiment_results_csv(db: Session = Depends(get_db)):
    """Generates and downloads a complete experiment audit log as a CSV spreadsheet."""
    output = io.StringIO()
    writer = csv.writer(output)

    # 1. Transactions Sheet
    writer.writerow(["=== TRANSACTIONS AUDIT LOG ==="])
    writer.writerow([
        "Transaction ID", "Client ID", "Base Version", "Committed Version",
        "Status", "Staleness", "Priority Score", "Submitted At", "Completed At"
    ])

    txns = db.query(Transaction).order_by(Transaction.submitted_at.asc()).all()
    for t in txns:
        writer.writerow([
            t.transaction_id,
            t.client_id,
            t.base_version_id,
            t.committed_version_id or "",
            t.status,
            t.staleness,
            t.priority_score,
            t.submitted_at.isoformat() if t.submitted_at else "",
            t.completed_at.isoformat() if t.completed_at else ""
        ])

    writer.writerow([])
    # 2. Model Versions Sheet
    writer.writerow(["=== MODEL VERSIONS LINEAGE ==="])
    writer.writerow(["Version ID", "Parent Version", "Version Number", "Loss", "Accuracy", "Created At"])
    versions = db.query(ModelVersion).order_by(ModelVersion.version_number.asc()).all()
    for v in versions:
        writer.writerow([
            v.version_id,
            v.parent_version_id or "ROOT",
            v.version_number,
            v.loss,
            v.accuracy,
            v.created_at.isoformat() if v.created_at else ""
        ])

    csv_content = output.getvalue()
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=mvcc_fl_experiment_results.csv"}
    )
