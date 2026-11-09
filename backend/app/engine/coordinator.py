"""
Central DBMS Transaction Coordinator for Asynchronous Federated Learning.
Orchestrates all 10 core DBMS modules:
MVCC, OCC, Adaptive Staleness, Priority Scheduler, Persistent WAL,
Crash Recovery, Selective Rollback, Garbage Collector, Conflict Predictor, and Differential Storage.
"""
from typing import Dict, Any, List, Optional, Tuple
import uuid
import threading
from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session
from app.config import settings, DATA_DIR
from app.db.models import Transaction, ModelVersion, ModelContribution, Client, ScheduleEntry
from app.engine.mvcc import MVCCVersionManager
from app.engine.occ import OCCValidationEngine
from app.engine.staleness import AdaptiveStalenessManager
from app.engine.scheduler import PriorityTransactionScheduler
from app.engine.wal import WALManager
from app.engine.recovery import CrashRecoveryManager
from app.engine.rollback import SelectiveRollbackManager
from app.engine.gc import MVCCGarbageCollector
from app.engine.predictor import TransactionConflictPredictor
from app.engine.differential import DifferentialStorageManager
from app.fl.aggregation import apply_weight_delta, compute_weight_norm
from app.fl.model import FraudDetectionNN, compute_model_metrics, set_flat_params
from app.fl.dataset import ensure_all_datasets_exist, FEATURE_COLUMNS

class DBMSTransactionCoordinator:
    """
    Central transaction coordinator maintaining strict ACID properties,
    multi-version snapshot isolation, optimistic concurrency control, and durable write-ahead logging.
    """
    def __init__(self):
        self._lock = threading.RLock()
        self._queue_state_lock = threading.RLock()
        self._drainer_active = False
        self._pending_transactions: Dict[str, Dict[str, Any]] = {}
        
        # 1. Initialize Sub-Engines
        self.mvcc = MVCCVersionManager()
        self.staleness_mgr = AdaptiveStalenessManager(
            base_threshold=settings.DEFAULT_STALENESS_THRESHOLD,
            max_allowance=settings.MAX_STALENESS_ALLOWANCE,
            cosine_threshold=settings.COSINE_SIMILARITY_THRESHOLD
        )
        self.occ = OCCValidationEngine(self.mvcc, self.staleness_mgr)
        self.scheduler = PriorityTransactionScheduler()
        self.wal = WALManager(settings.WAL_FILE_PATH)
        self.recovery = CrashRecoveryManager(self.wal, self.mvcc)
        self.rollback = SelectiveRollbackManager(self.mvcc, self.wal)
        self.gc = MVCCGarbageCollector(self.mvcc)
        self.predictor = TransactionConflictPredictor()
        self.differential = DifferentialStorageManager()

        # Cache validation sample dataset for coordinator-side evaluation
        self._eval_X: Optional[np.ndarray] = None
        self._eval_y: Optional[np.ndarray] = None

    def initialize(self, db: Session):
        """Hydrates coordinator memory state from database and disk checkpoints."""
        with self._lock:
            self.mvcc.load_from_db(db)
            all_ds = ensure_all_datasets_exist()
            if all_ds:
                sample_file = list(all_ds.values())[0][0]
                df = pd.read_csv(sample_file)
                self._eval_X = df[FEATURE_COLUMNS].values[:600].astype(np.float32)
                self._eval_y = df["is_fraud"].values[:600].astype(np.float32)

    def _evaluate_weights(self, weights: np.ndarray) -> Tuple[float, float]:
        """Computes loss and accuracy of weights on evaluation dataset."""
        if self._eval_X is None:
            return 0.5, 0.90
        model = FraudDetectionNN()
        set_flat_params(model, weights)
        return compute_model_metrics(model, self._eval_X, self._eval_y)

    def get_client_snapshot(self, client_id: str, db: Session) -> Tuple[str, np.ndarray]:
        """Read Phase: Client acquires snapshot isolation pin on head model version."""
        if self.recovery.is_crashed:
            raise RuntimeError("Coordinator is currently offline in simulated crash state. Recovery required.")
        return self.mvcc.get_snapshot(client_id, db=db)

    def submit_model_update(
        self,
        client_id: str,
        base_version_id: str,
        delta: np.ndarray,
        db: Session
    ) -> Dict[str, Any]:
        """
        Processes an incoming transaction through the full DBMS lifecycle:
        1. Predict conflict risk (advisory)
        2. Priority schedule & enqueue
        3. Write-Ahead Logging (BEGIN)
        4. OCC Validation (staleness & conflict)
        5. Atomic Commit with fsync guarantee
        6. MVCC version minting & differential metrics
        """
        if self.recovery.is_crashed:
            raise RuntimeError("Transaction rejected: Server is currently crashed. Run recovery to resume.")

        txn_id = f"tx_{uuid.uuid4().hex[:10]}"
        now = datetime.utcnow()
        current_vid = self.mvcc.current_version_id
        current_num = self.mvcc.current_version_number

        base_info = self.mvcc._versions.get(base_version_id)
        base_num = base_info["version_number"] if base_info else 0
        staleness = self.staleness_mgr.calculate_staleness(current_num, base_num)

        # Step 1: Create transaction record in relational catalog
        txn = Transaction(
            transaction_id=txn_id,
            client_id=client_id,
            base_version_id=base_version_id,
            status="PENDING",
            staleness=staleness,
            priority_score=1.0,
            submitted_at=now
        )
        db.add(txn)
        db.commit()

        # Step 2: Advisory Transaction Conflict Prediction (Module 9)
        prediction = self.predictor.predict_risk(
            txn_id=txn_id,
            client_id=client_id,
            staleness=staleness,
            client_delta=delta,
            current_queue_depth=self.scheduler.size(),
            db=db
        )

        # Enqueue and register a waiter atomically with respect to the queue
        # drainer. Concurrent callers wait for their own result while the
        # highest-priority queued transaction is processed next.
        completion = threading.Event()
        with self._queue_state_lock:
            self._pending_transactions[txn_id] = {
                "event": completion,
                "result": None,
                "error": None,
                "prediction": prediction,
                "submitted_staleness": staleness,
            }
            self.scheduler.enqueue(
                txn_id=txn_id,
                client_id=client_id,
                base_version_id=base_version_id,
                delta=delta,
                staleness=staleness,
                db=db,
            )
            should_drain = not self._drainer_active
            if should_drain:
                self._drainer_active = True

        if should_drain:
            self._drain_transaction_queue()

        completion.wait()
        with self._queue_state_lock:
            outcome = self._pending_transactions.pop(txn_id)
        if outcome["error"] is not None:
            raise RuntimeError(f"Transaction {txn_id} failed: {outcome['error']}")
        return outcome["result"]

    def _drain_transaction_queue(self):
        """Processes queued work in dynamic priority order, one durable commit at a time."""
        from app.db.session import SessionLocal

        while True:
            with self._queue_state_lock:
                item = self.scheduler.get_next()
                if item is None:
                    # Enqueue uses this same state lock, so no waiter can be
                    # stranded between the empty check and releasing ownership.
                    self._drainer_active = False
                    return
                pending = self._pending_transactions.get(item.transaction_id)

            session = SessionLocal()
            try:
                pending["result"] = self._process_queued_transaction(item, pending, session)
            except Exception as exc:
                session.rollback()
                pending["error"] = exc
            finally:
                try:
                    schedule = session.query(ScheduleEntry).filter_by(transaction_id=item.transaction_id).first()
                    if schedule:
                        schedule.queue_status = "DEQUEUED"
                        session.commit()
                finally:
                    session.close()
                    pending["event"].set()

    def _process_queued_transaction(self, item, pending: Dict[str, Any], db: Session) -> Dict[str, Any]:
        """Runs validation, WAL, and commit for the priority-selected queue item."""
        txn = db.query(Transaction).filter_by(transaction_id=item.transaction_id).one()
        schedule = txn.schedule_entry
        if schedule:
            schedule.queue_status = "PROCESSING"
            schedule.priority = item.priority_score
            schedule.waiting_time = max(0.0, (datetime.utcnow() - schedule.enqueued_at).total_seconds())
            db.commit()

        current_num = self.mvcc.current_version_number
        base_info = self.mvcc._versions.get(item.base_version_id)
        base_num = base_info["version_number"] if base_info else 0
        staleness = self.staleness_mgr.calculate_staleness(current_num, base_num)
        txn.staleness = staleness

        self.wal.log_begin(item.transaction_id, item.client_id, item.base_version_id, db=db)
        txn.status = "VALIDATING"
        db.commit()

        with self.occ._commit_lock:
            is_valid, val_status, conflict_score, scale_factor = self.occ.validate_transaction(
                transaction_id=item.transaction_id,
                client_id=item.client_id,
                base_version_id=item.base_version_id,
                client_delta=item.delta,
                db=db,
            )
            if not is_valid:
                self.wal.log_abort(item.transaction_id, item.client_id, reason=val_status, db=db)
                txn.status = "ABORTED"
                txn.completed_at = datetime.utcnow()
                db.commit()
                self.scheduler.record_client_failure(item.client_id)
                self.mvcc.release_snapshot(item.client_id, db=db)
                return {
                    "transaction_id": item.transaction_id,
                    "status": "ABORTED",
                    "validation_result": val_status,
                    "conflict_score": round(conflict_score, 4),
                    "staleness": staleness,
                    "prediction": pending["prediction"],
                }

            applied_delta = (item.delta * scale_factor).astype(np.float32)
            parent_vid = self.mvcc.current_version_id
            head_weights = self.mvcc.get_version_weights(parent_vid)
            new_weights = apply_weight_delta(head_weights, applied_delta, scaling_factor=1.0)
            loss, acc = self._evaluate_weights(new_weights)

            new_vid = f"v{self.mvcc.current_version_number + 1}"
            self.wal.log_update(item.transaction_id, item.client_id, item.base_version_id, applied_delta, db=db)
            delta_file = DATA_DIR / "deltas" / f"delta_{item.transaction_id}.npy"
            delta_file.parent.mkdir(parents=True, exist_ok=True)
            np.save(delta_file, applied_delta)
            self.wal.log_commit(item.transaction_id, item.client_id, committed_version=new_vid, db=db)

            published_vid = self.mvcc.create_version(
                parent_version_id=parent_vid,
                new_weights=new_weights,
                loss=loss,
                accuracy=acc,
                db=db,
            )
            if published_vid != new_vid:
                raise RuntimeError(f"Version sequence changed during commit: expected {new_vid}, got {published_vid}")

            db.add(ModelContribution(
                contribution_id=f"contrib_{item.transaction_id}",
                transaction_id=item.transaction_id,
                client_id=item.client_id,
                model_version_id=new_vid,
                update_reference=str(delta_file),
                weight_norm=compute_weight_norm(applied_delta),
                is_active=True,
                applied_at=datetime.utcnow(),
            ))
            self.differential.record_storage_metrics(new_weights, applied_delta)
            self.occ.record_committed_delta(self.mvcc.current_version_number, applied_delta)
            if self.wal._commit_count_since_checkpoint >= settings.CHECKPOINT_INTERVAL_TXNS:
                self.wal.create_checkpoint(new_vid, new_weights, db=db)

            txn.status = "COMMITTED"
            txn.committed_version_id = new_vid
            txn.completed_at = datetime.utcnow()
            db.commit()
            self.mvcc.release_snapshot(item.client_id, db=db)
            self.scheduler.record_client_success(item.client_id)

            return {
                "transaction_id": item.transaction_id,
                "status": "COMMITTED",
                "new_version_id": new_vid,
                "version_number": self.mvcc.current_version_number,
                "loss": round(loss, 4),
                "accuracy": round(acc, 4),
                "scaling_factor": round(scale_factor, 3),
                "staleness": staleness,
                "prediction": pending["prediction"],
            }
