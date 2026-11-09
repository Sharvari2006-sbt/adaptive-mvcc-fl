"""
Module 8: Adaptive MVCC Garbage Collector
Prunes unreferenced historical model version files and cache while preserving:
1. Pinned active client snapshots.
2. The current head model version.
3. Checkpoint baselines needed for recovery.
Reports disk storage usage before and after vacuum.
"""
from datetime import datetime
import os
from pathlib import Path
from typing import Dict, Any, List, Set, Tuple
from sqlalchemy.orm import Session
from app.config import CHECKPOINTS_DIR
from app.db.models import ModelVersion
from app.engine.mvcc import MVCCVersionManager

class MVCCGarbageCollector:
    """
    Background garbage collection engine for multi-version model store.
    """
    def __init__(self, mvcc: MVCCVersionManager):
        self.mvcc = mvcc
        self._last_gc_stats: Dict[str, Any] = {}

    def _get_checkpoints_dir_size_bytes(self) -> int:
        total = 0
        if CHECKPOINTS_DIR.exists():
            for p in CHECKPOINTS_DIR.glob("*"):
                if p.is_file():
                    total += p.stat().st_size
        return total

    def run_garbage_collection(self, db: Session, keep_latest_n: int = 3) -> Dict[str, Any]:
        """
        Executes snapshot-aware garbage collection:
        1. Queries active snapshots from MVCC pins.
        2. Identifies pinned versions and preserves them.
        3. Identifies versions older than horizon not needed for rollback/recovery.
        4. Reclaims memory and safely unlinks obsolete checkpoint files.
        """
        bytes_before = self._get_checkpoints_dir_size_bytes()
        
        # 1. Collect protected versions
        active_pins = self.mvcc.get_active_pins()
        pinned_vids: Set[str] = set(active_pins.values())
        current_vid = self.mvcc.current_version_id
        
        # Protect pinned snapshots, current head, and genesis v0
        protected_vids: Set[str] = {"v0", current_vid}.union(pinned_vids)

        # Protect the latest N versions
        all_versions = db.query(ModelVersion).order_by(ModelVersion.version_number.desc()).all()
        for v in all_versions[:keep_latest_n]:
            protected_vids.add(v.version_id)

        # 2. Identify safe-to-delete versions
        pruned_versions: List[str] = []
        freed_bytes = 0

        for v in all_versions:
            vid = v.version_id
            if vid not in protected_vids:
                # Version is not pinned by any client, is not head, is not genesis, and is outside keep window
                # Prune in-memory weight tensor
                self.mvcc.prune_version_cache(vid)

                # Remove physical checkpoint file if safe
                ckpt_path = Path(v.checkpoint_path)
                if ckpt_path.exists() and vid != "v0":
                    file_size = ckpt_path.stat().st_size
                    try:
                        ckpt_path.unlink()
                        freed_bytes += file_size
                        pruned_versions.append(vid)
                    except OSError:
                        pass

        bytes_after = self._get_checkpoints_dir_size_bytes()

        self._last_gc_stats = {
            "timestamp": datetime.utcnow().isoformat(),
            "active_client_pins": active_pins,
            "protected_versions": list(protected_vids),
            "pruned_versions": pruned_versions,
            "storage_before_bytes": bytes_before,
            "storage_after_bytes": bytes_after,
            "bytes_reclaimed": freed_bytes,
            "reclaimed_mb": round(freed_bytes / (1024 * 1024), 4)
        }

        return self._last_gc_stats

    def get_last_stats(self) -> Dict[str, Any]:
        return self._last_gc_stats
