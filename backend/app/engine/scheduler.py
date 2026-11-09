"""
Module 4: Priority-Based Transaction Scheduler
Implements starvation-free transaction queue with dynamic priority calculation:
Priority = w_wait * wait_time - w_stale * staleness + w_fail * failure_history + aging_boost
"""
from typing import Dict, Any, List, Optional
import time
import heapq
import threading
from datetime import datetime
from sqlalchemy.orm import Session
from app.config import settings
from app.db.models import ScheduleEntry, Transaction

class QueuedTransaction:
    """Represents a transaction residing in the scheduler priority queue."""
    def __init__(
        self,
        transaction_id: str,
        client_id: str,
        base_version_id: str,
        delta: Any,
        staleness: int,
        failure_count: int = 0
    ):
        self.transaction_id = transaction_id
        self.client_id = client_id
        self.base_version_id = base_version_id
        self.delta = delta
        self.staleness = staleness
        self.failure_count = failure_count
        self.enqueued_at = time.time()
        self.priority_score: float = 0.0

    def compute_priority(self, now: float) -> float:
        """
        Dynamically computes priority score with aging to prevent starvation:
        P = (w_wait * wait_time) - (w_stale * staleness) + (w_fail * failures) + (aging_rate * wait_time^1.1)
        """
        wait_time = max(0.0, now - self.enqueued_at)
        p = (
            settings.WAITING_TIME_WEIGHT * wait_time
            - settings.STALENESS_PENALTY_WEIGHT * self.staleness
            + settings.FAILURE_RECOVERY_WEIGHT * self.failure_count
            + settings.STARVATION_AGING_RATE * (wait_time ** 1.1)
        )
        self.priority_score = float(p)
        return self.priority_score

    def __lt__(self, other: "QueuedTransaction") -> bool:
        # Higher priority score comes first in max-heap (implemented via reversed comparison)
        return self.priority_score > other.priority_score


class PriorityTransactionScheduler:
    """Manages transaction scheduling queue and ensures starvation-free concurrency."""
    def __init__(self):
        self._lock = threading.Lock()
        self._queue: List[QueuedTransaction] = []
        self._client_failure_history: Dict[str, int] = {}

    def record_client_failure(self, client_id: str):
        """Records a validation failure to boost priority on subsequent retry."""
        with self._lock:
            self._client_failure_history[client_id] = self._client_failure_history.get(client_id, 0) + 1

    def record_client_success(self, client_id: str):
        """Resets client failure count upon successful commit."""
        with self._lock:
            self._client_failure_history[client_id] = max(0, self._client_failure_history.get(client_id, 0) - 1)

    def enqueue(
        self,
        txn_id: str,
        client_id: str,
        base_version_id: str,
        delta: Any,
        staleness: int,
        db: Optional[Session] = None
    ) -> QueuedTransaction:
        """Enqueues transaction and records schedule entry."""
        with self._lock:
            failures = self._client_failure_history.get(client_id, 0)
            item = QueuedTransaction(
                transaction_id=txn_id,
                client_id=client_id,
                base_version_id=base_version_id,
                delta=delta,
                staleness=staleness,
                failure_count=failures
            )
            item.compute_priority(time.time())
            self._queue.append(item)

            if db:
                entry = ScheduleEntry(
                    schedule_id=f"sched_{txn_id}",
                    transaction_id=txn_id,
                    priority=item.priority_score,
                    waiting_time=0.0,
                    queue_status="QUEUED",
                    enqueued_at=datetime.utcnow()
                )
                db.add(entry)
                db.commit()

            return item

    def get_next(self, db: Optional[Session] = None) -> Optional[QueuedTransaction]:
        """Picks the transaction with the highest priority after updating all aging scores."""
        with self._lock:
            if not self._queue:
                return None

            now = time.time()
            for item in self._queue:
                item.compute_priority(now)

            # Sort descending by priority score
            self._queue.sort(key=lambda x: x.priority_score, reverse=True)
            chosen = self._queue.pop(0)

            if db:
                db_entry = db.query(ScheduleEntry).filter(ScheduleEntry.transaction_id == chosen.transaction_id).first()
                if db_entry:
                    db_entry.queue_status = "PROCESSING"
                    db_entry.priority = chosen.priority_score
                    db_entry.waiting_time = now - chosen.enqueued_at
                    db.commit()

            return chosen

    def get_queue_status(self) -> List[Dict[str, Any]]:
        """Returns snapshot of current queue state with recalculated priorities."""
        with self._lock:
            now = time.time()
            for item in self._queue:
                item.compute_priority(now)
            
            sorted_items = sorted(self._queue, key=lambda x: x.priority_score, reverse=True)
            return [
                {
                    "transaction_id": item.transaction_id,
                    "client_id": item.client_id,
                    "base_version_id": item.base_version_id,
                    "staleness": item.staleness,
                    "failure_count": item.failure_count,
                    "waiting_time_seconds": round(max(0.0, now - item.enqueued_at), 2),
                    "priority_score": round(item.priority_score, 3)
                }
                for item in sorted_items
            ]

    def size(self) -> int:
        with self._lock:
            return len(self._queue)
