"""
Module 1: Custom MVCC Version Manager
Maintains model version lineage DAG, snapshot isolation, and active reader pins.
"""
from datetime import datetime
import threading
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
import numpy as np
from sqlalchemy.orm import Session
from app.config import CHECKPOINTS_DIR, settings
from app.db.models import ModelVersion

class MVCCVersionManager:
    """
    Manages multi-version concurrency control for model weights.
    Provides snapshot isolation: clients train against pinned historical snapshots
    without blocking incoming commits or being affected by concurrent updates.
    """
    def __init__(self):
        self._lock = threading.RLock()
        # In-memory fast cache: version_id -> {"number": int, "parent": str, "weights": np.ndarray, "loss": float, "acc": float, "created_at": datetime}
        self._versions: Dict[str, Dict[str, Any]] = {}
        # Client pins: client_id -> pinned version_id
        self._client_pins: Dict[str, str] = {}
        # Active reader counts: version_id -> int
        self._active_readers: Dict[str, int] = {}
        # Current latest committed version ID
        self._current_version_id: Optional[str] = None
        self._current_version_number: int = 0

    def load_from_db(self, db: Session):
        """Loads version metadata from database and hydrates memory state."""
        with self._lock:
            self._versions.clear()
            self._active_readers.clear()
            self._current_version_id = None
            self._current_version_number = 0
            db_versions = db.query(ModelVersion).order_by(ModelVersion.version_number.asc()).all()
            for v in db_versions:
                weights = None
                if Path(v.checkpoint_path).exists():
                    weights = np.load(v.checkpoint_path)
                
                self._versions[v.version_id] = {
                    "version_id": v.version_id,
                    "parent_version_id": v.parent_version_id,
                    "version_number": v.version_number,
                    "checkpoint_path": v.checkpoint_path,
                    "loss": v.loss,
                    "accuracy": v.accuracy,
                    "created_at": v.created_at,
                    "weights": weights
                }
                self._active_readers[v.version_id] = v.active_readers
                if v.version_number >= self._current_version_number:
                    self._current_version_id = v.version_id
                    self._current_version_number = v.version_number

    @property
    def current_version_id(self) -> str:
        with self._lock:
            return self._current_version_id or "v0"

    @property
    def current_version_number(self) -> int:
        with self._lock:
            return self._current_version_number

    def get_snapshot(self, client_id: str, db: Optional[Session] = None) -> Tuple[str, np.ndarray]:
        """
        Snapshot Read Phase: Pins the current head model version for a client.
        Increments active reader count and returns (version_id, model_weights).
        """
        with self._lock:
            target_vid = self.current_version_id
            
            # Release any previous snapshot held by this client
            self.release_snapshot(client_id, db=db)
            
            self._client_pins[client_id] = target_vid
            self._active_readers[target_vid] = self._active_readers.get(target_vid, 0) + 1
            
            if db:
                db_v = db.query(ModelVersion).filter(ModelVersion.version_id == target_vid).first()
                if db_v:
                    db_v.active_readers = self._active_readers[target_vid]
                    db.commit()

            weights = self.get_version_weights(target_vid)
            return target_vid, weights.copy()

    def release_snapshot(self, client_id: str, db: Optional[Session] = None):
        """Releases the snapshot pin held by a client."""
        with self._lock:
            old_vid = self._client_pins.pop(client_id, None)
            if old_vid and old_vid in self._active_readers:
                self._active_readers[old_vid] = max(0, self._active_readers[old_vid] - 1)
                if db:
                    db_v = db.query(ModelVersion).filter(ModelVersion.version_id == old_vid).first()
                    if db_v:
                        db_v.active_readers = self._active_readers[old_vid]
                        db.commit()

    def get_version_weights(self, version_id: str) -> np.ndarray:
        """Retrieves model weights for a specific version ID."""
        with self._lock:
            v_info = self._versions.get(version_id)
            if not v_info:
                raise ValueError(f"Model version {version_id} not found in MVCC store.")
            
            if v_info.get("weights") is not None:
                return v_info["weights"]
            
            # Load from checkpoint disk file
            cpath = Path(v_info["checkpoint_path"])
            if cpath.exists():
                weights = np.load(cpath)
                v_info["weights"] = weights
                return weights
            else:
                raise FileNotFoundError(f"Checkpoint file {cpath} missing for version {version_id}.")

    def create_version(
        self,
        parent_version_id: str,
        new_weights: np.ndarray,
        loss: float,
        accuracy: float,
        db: Session
    ) -> str:
        """
        Creates a new immutable model version node in the MVCC DAG.
        Updates head pointer atomically.
        """
        with self._lock:
            new_num = self._current_version_number + 1
            new_vid = f"v{new_num}"
            checkpoint_file = CHECKPOINTS_DIR / f"{new_vid}_checkpoint.npy"
            np.save(checkpoint_file, new_weights.astype(np.float32))

            now = datetime.utcnow()
            # 1. Update in-memory registry
            self._versions[new_vid] = {
                "version_id": new_vid,
                "parent_version_id": parent_version_id,
                "version_number": new_num,
                "checkpoint_path": str(checkpoint_file),
                "loss": loss,
                "accuracy": accuracy,
                "created_at": now,
                "weights": new_weights.copy()
            }
            self._active_readers[new_vid] = 0
            self._current_version_id = new_vid
            self._current_version_number = new_num

            # 2. Persist to relational catalog
            db_v = ModelVersion(
                version_id=new_vid,
                parent_version_id=parent_version_id,
                version_number=new_num,
                checkpoint_path=str(checkpoint_file),
                active_readers=0,
                loss=loss,
                accuracy=accuracy,
                created_at=now
            )
            db.add(db_v)
            db.commit()

            return new_vid

    def get_lineage(self) -> List[Dict[str, Any]]:
        """Returns ordered list of all model versions with parent-child links."""
        with self._lock:
            ordered = sorted(self._versions.values(), key=lambda x: x["version_number"])
            return [
                {
                    "version_id": v["version_id"],
                    "parent_version_id": v["parent_version_id"],
                    "version_number": v["version_number"],
                    "loss": round(float(v["loss"]), 4),
                    "accuracy": round(float(v["accuracy"]), 4),
                    "active_readers": self._active_readers.get(v["version_id"], 0),
                    "is_current": (v["version_id"] == self._current_version_id),
                    "created_at": v["created_at"].isoformat() if hasattr(v["created_at"], "isoformat") else str(v["created_at"])
                }
                for v in ordered
            ]

    def get_active_pins(self) -> Dict[str, str]:
        """Returns snapshot mapping: {client_id: version_id}."""
        with self._lock:
            return dict(self._client_pins)

    def prune_version_cache(self, version_id: str):
        """Releases heavy weight tensors from RAM while keeping metadata intact."""
        with self._lock:
            if version_id in self._versions and version_id != self._current_version_id:
                if self._active_readers.get(version_id, 0) == 0:
                    self._versions[version_id]["weights"] = None
