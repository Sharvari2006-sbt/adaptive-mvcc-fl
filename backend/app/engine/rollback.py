"""
Module 7: Selective Rollback Manager
Deterministically purges poisoned or malicious model contributions by replaying historical
valid updates from a prior checkpoint without mutating append-only WAL records.
"""
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
import numpy as np
from sqlalchemy.orm import Session
from app.config import CHECKPOINTS_DIR
from app.db.models import RollbackEvent, ModelContribution, ModelVersion, Transaction
from app.engine.mvcc import MVCCVersionManager
from app.engine.wal import WALManager
from app.fl.aggregation import apply_weight_delta
from app.fl.model import FraudDetectionNN, compute_model_metrics, set_flat_params
from app.fl.dataset import ensure_all_datasets_exist, FEATURE_COLUMNS
import pandas as pd

class SelectiveRollbackManager:
    """
    Executes selective rollback of poisoned model updates.
    Preserves audit immutability by appending COMPENSATION records rather than altering WAL history.
    """
    def __init__(self, mvcc: MVCCVersionManager, wal: WALManager):
        self.mvcc = mvcc
        self.wal = wal

    def rollback_transaction(
        self,
        target_transaction_id: str,
        reason: str,
        db: Session
    ) -> Dict[str, Any]:
        """
        Reconstructs the global model excluding target_transaction_id:
        1. Identifies all committed model contributions in historical order.
        2. Retrieves baseline weights prior to target transaction.
        3. Deterministically re-aggregates only valid contributions.
        4. Mints a new corrected model version V_clean.
        5. Logs COMPENSATION in WAL and records ROLLBACK_EVENT in relational catalog.
        """
        # 1. Verify target transaction exists
        target_txn = db.query(Transaction).filter(Transaction.transaction_id == target_transaction_id).first()
        if not target_txn:
            raise ValueError(f"Target transaction {target_transaction_id} not found.")

        # 2. Query all active contributions in historical sequence
        contributions = (
            db.query(ModelContribution)
            .order_by(ModelContribution.applied_at.asc())
            .all()
        )

        if not contributions:
            raise ValueError("No historical model contributions recorded for reconstruction.")

        # 3. Load baseline weights (Genesis V0 checkpoint)
        v0_path = CHECKPOINTS_DIR / "v0_checkpoint.npy"
        if not v0_path.exists():
            from app.fl.model import get_initial_weights
            reconstructed_weights = get_initial_weights()
        else:
            reconstructed_weights = np.load(v0_path)

        replayed_txns = []
        skipped_txns = []

        # 4. Replay valid updates, skipping target_transaction_id
        for contrib in contributions:
            if contrib.transaction_id == target_transaction_id:
                # Mark inactive in relational store
                contrib.is_active = False
                skipped_txns.append(contrib.transaction_id)
                continue

            if not contrib.is_active:
                # Previously rolled back
                skipped_txns.append(contrib.transaction_id)
                continue

            # Load delta from file
            delta_file = Path(contrib.update_reference)
            if delta_file.exists():
                delta = np.load(delta_file)
                reconstructed_weights = apply_weight_delta(reconstructed_weights, delta, scaling_factor=1.0)
                replayed_txns.append(contrib.transaction_id)

        # 5. Compute loss and accuracy on sample validation dataset
        all_ds = ensure_all_datasets_exist()
        sample_path = list(all_ds.values())[0][0]
        sample_df = pd.read_csv(sample_path)
        X_eval = sample_df[FEATURE_COLUMNS].values[:500].astype(np.float32)
        y_eval = sample_df["is_fraud"].values[:500].astype(np.float32)

        model = FraudDetectionNN()
        set_flat_params(model, reconstructed_weights)
        loss, acc = compute_model_metrics(model, X_eval, y_eval)

        # 6. Mint new corrected model version in MVCC
        corrected_vid = self.mvcc.create_version(
            parent_version_id=self.mvcc.current_version_id,
            new_weights=reconstructed_weights,
            loss=loss,
            accuracy=acc,
            db=db
        )

        # 7. Append COMPENSATION record to WAL
        wal_rec = self.wal.append_record(
            record_type="COMPENSATION",
            txn_id=target_transaction_id,
            client_id=target_txn.client_id,
            base_version=self.mvcc.current_version_id,
            data_reference=f"ROLLED_BACK_TO_{corrected_vid}",
            db=db,
            force_fsync=True
        )

        # 8. Record RollbackEvent in catalog
        rb_event = RollbackEvent(
            rollback_id=f"rb_{target_transaction_id}_{int(datetime.utcnow().timestamp())}",
            target_transaction_id=target_transaction_id,
            restored_version_id=corrected_vid,
            reason=reason,
            rollback_at=datetime.utcnow(),
            status="SUCCESS"
        )
        db.add(rb_event)
        
        # Update target txn status to ABORTED_POISONED
        target_txn.status = "ABORTED"
        db.commit()

        return {
            "rollback_id": rb_event.rollback_id,
            "target_transaction_id": target_transaction_id,
            "reconstructed_version_id": corrected_vid,
            "replayed_transactions_count": len(replayed_txns),
            "skipped_transactions": skipped_txns,
            "loss_after_rollback": round(loss, 4),
            "accuracy_after_rollback": round(acc, 4),
            "wal_compensation_lsn": wal_rec["lsn"],
            "status": "ROLLBACK_SUCCESS"
        }
