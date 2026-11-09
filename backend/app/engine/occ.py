"""
Module 2: Optimistic Concurrency Control (OCC) Validation Engine
Enforces multi-phase OCC validation:
1. Read Phase: Client computes update on snapshot V_base.
2. Validation Phase: Detects write-write conflicts, parameter divergence, and staleness bounds.
3. Write/Commit Phase: Serialized atomic commit with WAL flush.
"""
from datetime import datetime
import threading
from typing import Dict, Any, Optional, Tuple, List
import numpy as np
from sqlalchemy.orm import Session
from app.db.models import Transaction, Validation, ModelContribution
from app.engine.mvcc import MVCCVersionManager
from app.engine.staleness import AdaptiveStalenessManager

class OCCValidationEngine:
    """
    Optimistic Concurrency Control engine tailored for AFL model updates.
    Prevents parameter overwrites and lost updates while maximizing asynchronous throughput.
    """
    def __init__(
        self,
        mvcc_manager: MVCCVersionManager,
        staleness_manager: AdaptiveStalenessManager,
        conflict_norm_threshold: float = 0.75
    ):
        self.mvcc = mvcc_manager
        self.staleness_mgr = staleness_manager
        self.conflict_norm_threshold = conflict_norm_threshold
        # Atomic commit lock to prevent race conditions during validation and commit
        self._commit_lock = threading.Lock()
        # History of recent committed deltas: list of (version_num, delta_vector)
        self._recent_deltas: List[Tuple[int, np.ndarray]] = []
        self._max_delta_history = 20

    def record_committed_delta(self, version_num: int, delta: np.ndarray):
        """Maintains ring buffer of recent deltas for conflict and staleness trajectory analysis."""
        self._recent_deltas.append((version_num, delta.copy()))
        if len(self._recent_deltas) > self._max_delta_history:
            self._recent_deltas.pop(0)

    def get_intervening_delta(self, base_version_num: int) -> Optional[np.ndarray]:
        """Calculates the cumulative delta of all transactions committed since base_version_num."""
        deltas = [d for v_num, d in self._recent_deltas if v_num > base_version_num]
        if not deltas:
            return None
        return np.sum(deltas, axis=0)

    def validate_transaction(
        self,
        transaction_id: str,
        client_id: str,
        base_version_id: str,
        client_delta: np.ndarray,
        db: Session
    ) -> Tuple[bool, str, float, float]:
        """
        Validates an optimistic transaction against the current state of the global model.
        Returns:
            (is_valid: bool, status: str, conflict_score: float, scaling_factor: float)
        """
        current_vid = self.mvcc.current_version_id
        current_num = self.mvcc.current_version_number

        base_info = self.mvcc._versions.get(base_version_id)
        if not base_info:
            return False, "ABORTED_INVALID_BASE_VERSION", 1.0, 0.0

        base_num = base_info["version_number"]
        staleness = self.staleness_mgr.calculate_staleness(current_num, base_num)

        # 1. Evaluate staleness
        intervening_delta = self.get_intervening_delta(base_num)
        is_stale_ok, stale_reason, utility, scale = self.staleness_mgr.evaluate_staleness(
            staleness, client_delta, intervening_delta
        )

        if not is_stale_ok:
            # Staleness validation failed
            val_record = Validation(
                validation_id=f"val_{transaction_id}",
                transaction_id=transaction_id,
                validation_result="REJECTED_STALE",
                conflict_score=1.0 - utility,
                failure_reason=stale_reason,
                checked_at=datetime.utcnow()
            )
            db.add(val_record)
            db.commit()
            return False, "REJECTED_STALE", 1.0 - utility, 0.0

        # 2. Evaluate write-write conflict with intervening committed updates
        conflict_score = 0.0
        if intervening_delta is not None and staleness > 0:
            # Measure directional conflict (negative cosine indicates direct parameter opposition)
            norm_c = np.linalg.norm(client_delta)
            norm_i = np.linalg.norm(intervening_delta)
            if norm_c > 1e-7 and norm_i > 1e-7:
                cos_sim = float(np.dot(client_delta, intervening_delta) / (norm_c * norm_i))
                # Negative cosine similarity indicates destructive interference
                if cos_sim < -self.conflict_norm_threshold:
                    conflict_score = abs(cos_sim)
                    val_record = Validation(
                        validation_id=f"val_{transaction_id}",
                        transaction_id=transaction_id,
                        validation_result="REJECTED_CONFLICT",
                        conflict_score=conflict_score,
                        failure_reason=f"Destructive parameter clash (cos_sim={cos_sim:.3f})",
                        checked_at=datetime.utcnow()
                    )
                    db.add(val_record)
                    db.commit()
                    return False, "REJECTED_CONFLICT", conflict_score, 0.0

        # 3. Passed validation
        val_record = Validation(
            validation_id=f"val_{transaction_id}",
            transaction_id=transaction_id,
            validation_result="PASSED",
            conflict_score=conflict_score,
            failure_reason=None,
            checked_at=datetime.utcnow()
        )
        db.add(val_record)
        db.commit()
        return True, "PASSED", conflict_score, scale
