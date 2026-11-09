"""
Module 6: Crash Recovery Manager
Implements ARIES-style recovery:
1. Analysis: Scan WAL from latest valid checkpoint forward to identify committed vs uncommitted transactions.
2. Redo: Replay all committed updates post-checkpoint in strict LSN sequence.
3. Undo: Ignore/abort all in-flight or uncommitted transactions at crash time.
Restores the last consistent model state and rehydrates MVCC version store.
"""
from datetime import datetime
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
from sqlalchemy.orm import Session
from app.config import CHECKPOINTS_DIR
from app.db.models import ModelVersion, Transaction, ModelContribution
from app.engine.mvcc import MVCCVersionManager
from app.engine.wal import WALManager
from app.utils.serialization import deserialize_sparse_delta

class CrashRecoveryManager:
    """
    Manages crash simulation and durable state recovery using Write-Ahead Logs and checkpoints.
    """
    def __init__(self, wal_manager: WALManager, mvcc_manager: MVCCVersionManager):
        self.wal = wal_manager
        self.mvcc = mvcc_manager
        self._is_crashed = False
        self._last_recovery_stats: Dict[str, Any] = {}

    @property
    def is_crashed(self) -> bool:
        return self._is_crashed

    def simulate_crash(self):
        """Simulates an abrupt server termination: uncommitted in-memory transactions vanish."""
        self._is_crashed = True
        # Clear in-memory client pins and active cache
        self.mvcc._client_pins.clear()
        self.mvcc._active_readers.clear()

    def restart_and_recover(self, db: Session) -> Dict[str, Any]:
        """
        Executes ARIES recovery:
        Reads latest checkpoint, replays committed WAL updates, restores consistent model version.
        """
        start_time = time.perf_counter()
        records = self.wal.read_all_records()
        integrity_ok, corrupted_lsns = self.wal.verify_integrity()
        if not integrity_ok:
            raise ValueError(f"WAL integrity check failed at LSNs: {corrupted_lsns}")

        # Step 1: Analysis Phase - Scan backwards for latest valid CHECKPOINT
        checkpoint_record = None
        checkpoint_idx = -1
        for i in range(len(records) - 1, -1, -1):
            if records[i].get("record_type") == "CHECKPOINT":
                checkpoint_record = records[i]
                checkpoint_idx = i
                break

        # Load baseline weights from checkpoint or genesis v0
        if checkpoint_record and Path(checkpoint_record.get("data_reference", "")).exists():
            base_weights = np.load(checkpoint_record["data_reference"])
            base_version = checkpoint_record.get("base_version", "v0")
            ckpt_lsn = checkpoint_record.get("lsn", 0)
        else:
            v0_path = CHECKPOINTS_DIR / "v0_checkpoint.npy"
            if v0_path.exists():
                base_weights = np.load(v0_path)
            else:
                from app.fl.model import get_initial_weights
                base_weights = get_initial_weights()
            base_version = "v0"
            ckpt_lsn = 0
            checkpoint_idx = -1

        # Scan records after checkpoint to classify transactions
        post_ckpt_records = records[checkpoint_idx + 1:] if checkpoint_idx >= 0 else records
        
        committed_txns = set()
        commit_records: Dict[str, Dict[str, Any]] = {}
        aborted_txns = set()
        active_txns = set()
        txn_updates: Dict[str, Dict[str, Any]] = {}

        for r in post_ckpt_records:
            rtype = r.get("record_type")
            tid = r.get("transaction_id")
            if not tid:
                continue

            if rtype == "BEGIN":
                active_txns.add(tid)
            elif rtype == "UPDATE":
                txn_updates[tid] = r
            elif rtype == "COMMIT":
                committed_txns.add(tid)
                commit_records[tid] = r
                active_txns.discard(tid)
            elif rtype == "ABORT":
                aborted_txns.add(tid)
                active_txns.discard(tid)

        # Incomplete transactions: active at crash time but never committed
        incomplete_txns = list(active_txns - committed_txns - aborted_txns)

        # Step 2: Redo Phase - Replay committed transactions in strict LSN sequence
        current_recovered_weights = base_weights.copy()
        redo_count = 0
        replayed_txns = []

        recovered_parent = base_version
        for r in post_ckpt_records:
            if r.get("record_type") == "UPDATE" and r.get("transaction_id") in committed_txns:
                sparse = r.get("sparse_delta")
                if sparse:
                    delta = deserialize_sparse_delta(sparse)
                    current_recovered_weights += delta
                    redo_count += 1
                    tid = r["transaction_id"]
                    replayed_txns.append(tid)

                    # A durable COMMIT may exist even if the process died
                    # before publishing its version row/checkpoint. Complete
                    # that publication during redo, using the version named by
                    # the commit record.
                    commit = commit_records[tid]
                    committed_vid = commit.get("data_reference")
                    db_version = db.query(ModelVersion).filter(ModelVersion.version_id == committed_vid).first()
                    if committed_vid and db_version is None:
                        version_number = int(committed_vid[1:])
                        checkpoint_path = CHECKPOINTS_DIR / f"{committed_vid}_checkpoint.npy"
                        np.save(checkpoint_path, current_recovered_weights.astype(np.float32))
                        db.add(ModelVersion(
                            version_id=committed_vid,
                            parent_version_id=recovered_parent,
                            version_number=version_number,
                            checkpoint_path=str(checkpoint_path),
                            active_readers=0,
                            loss=0.0,
                            accuracy=0.0,
                            created_at=datetime.utcnow()
                        ))
                        db.flush()
                    if committed_vid:
                        recovered_parent = committed_vid
                    db_txn = db.query(Transaction).filter(Transaction.transaction_id == tid).first()
                    if db_txn:
                        db_txn.status = "COMMITTED"
                        db_txn.committed_version_id = committed_vid
                        db_txn.completed_at = db_txn.completed_at or datetime.utcnow()
                        contribution = db.query(ModelContribution).filter(
                            ModelContribution.transaction_id == tid
                        ).first()
                        if contribution is None:
                            delta_path = CHECKPOINTS_DIR.parent / "deltas" / f"delta_{tid}.npy"
                            delta_path.parent.mkdir(parents=True, exist_ok=True)
                            np.save(delta_path, delta.astype(np.float32))
                            db.add(ModelContribution(
                                contribution_id=f"contrib_{tid}",
                                transaction_id=tid,
                                client_id=db_txn.client_id,
                                model_version_id=committed_vid,
                                update_reference=str(delta_path),
                                weight_norm=float(np.linalg.norm(delta)),
                                is_active=True,
                                applied_at=datetime.utcnow()
                            ))

        # Step 3: Undo Phase - Mark uncommitted / incomplete transactions as ABORTED in database
        active_rows = db.query(Transaction).filter(Transaction.status.in_(["PENDING", "VALIDATING"])).all()
        for db_txn in active_rows:
            if db_txn.transaction_id not in committed_txns:
                if db_txn.transaction_id not in incomplete_txns:
                    incomplete_txns.append(db_txn.transaction_id)
                db_txn.status = "ABORTED"
                db_txn.completed_at = datetime.utcnow()
        db.commit()

        # Step 4: Rehydrate MVCC state
        self.mvcc.load_from_db(db)
        
        # Determine highest committed version
        recovered_vid = self.mvcc.current_version_id
        duration_ms = (time.perf_counter() - start_time) * 1000.0

        self._is_crashed = False
        self._last_recovery_stats = {
            "checkpoint_lsn": ckpt_lsn,
            "total_wal_records": len(records),
            "committed_txns_recovered": len(committed_txns),
            "incomplete_txns_discarded": len(incomplete_txns),
            "redo_updates_applied": redo_count,
            "recovered_version_id": recovered_vid,
            "replayed_transactions": replayed_txns,
            "recovery_duration_ms": round(duration_ms, 2),
            "status": "RECOVERY_COMPLETE"
        }

        return self._last_recovery_stats

    def get_last_recovery_stats(self) -> Dict[str, Any]:
        return self._last_recovery_stats
