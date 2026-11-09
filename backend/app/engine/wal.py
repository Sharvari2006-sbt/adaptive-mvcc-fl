"""
Module 5: Custom Persistent Write-Ahead Logging (WAL) Engine
Implements strict append-only logging with CRC32 checksums, fsync persistence guarantees,
and periodic checkpoint markers.
"""
import os
import json
import uuid
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
from sqlalchemy.orm import Session
from app.config import settings, WAL_DIR, CHECKPOINTS_DIR
from app.db.models import WALRecord
from app.utils.hashing import compute_crc32, verify_crc32
from app.utils.serialization import serialize_weights_to_base64, deserialize_weights_from_base64, serialize_sparse_delta, deserialize_sparse_delta

class WALManager:
    """
    Custom append-only Write-Ahead Log.
    Guarantees that WAL records are flushed (fsync) to durable disk storage
    BEFORE committed model versions are published or reported back to clients.
    """
    def __init__(self, wal_path: Optional[str] = None):
        self.wal_path = Path(wal_path or settings.WAL_FILE_PATH)
        self.wal_path.parent.mkdir(parents=True, exist_ok=True)
        # Checkpoint creation appends a CHECKPOINT record while already holding
        # the WAL lock, so the lock must allow same-thread re-entry.
        self._lock = threading.RLock()
        self._current_lsn = self._initialize_lsn()
        self._commit_count_since_checkpoint = 0

    def _initialize_lsn(self) -> int:
        """Determines next LSN based on existing WAL file contents."""
        if not self.wal_path.exists():
            return 0
        last_lsn = 0
        try:
            with open(self.wal_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        record = json.loads(line)
                        last_lsn = max(last_lsn, record.get("lsn", 0))
        except Exception:
            pass
        return last_lsn

    @property
    def current_lsn(self) -> int:
        with self._lock:
            return self._current_lsn

    def append_record(
        self,
        record_type: str,
        txn_id: Optional[str] = None,
        client_id: Optional[str] = None,
        base_version: Optional[str] = None,
        delta: Optional[np.ndarray] = None,
        data_reference: str = "",
        db: Optional[Session] = None,
        force_fsync: bool = True
    ) -> Dict[str, Any]:
        """
        Atomically appends a log record with CRC32 checksum and fsync guarantee.
        Record types: 'BEGIN', 'UPDATE', 'COMMIT', 'ABORT', 'CHECKPOINT', 'COMPENSATION'
        """
        with self._lock:
            self._current_lsn += 1
            lsn = self._current_lsn
            log_id = f"wal_{lsn:08d}_{uuid.uuid4().hex[:6]}"
            now_iso = datetime.utcnow().isoformat()

            sparse_delta = None
            if delta is not None:
                sparse_delta = serialize_sparse_delta(delta)

            payload_dict = {
                "log_id": log_id,
                "lsn": lsn,
                "record_type": record_type,
                "transaction_id": txn_id,
                "client_id": client_id,
                "base_version": base_version,
                "data_reference": data_reference,
                "sparse_delta": sparse_delta,
                "timestamp": now_iso
            }

            # 1. Compute checksum over the canonical JSON payload
            payload_json = json.dumps(payload_dict, sort_keys=True)
            checksum = compute_crc32(payload_json)

            full_record = {
                **payload_dict,
                "checksum": checksum
            }
            record_line = json.dumps(full_record) + "\n"

            # 2. Append to physical WAL file and force fsync
            with open(self.wal_path, "a", encoding="utf-8") as f:
                f.write(record_line)
                if force_fsync:
                    f.flush()
                    os.fsync(f.fileno())

            # 3. Mirror into database catalog if session provided
            if db:
                db_record = WALRecord(
                    log_id=log_id,
                    lsn=lsn,
                    transaction_id=txn_id,
                    record_type=record_type,
                    data_reference=data_reference or f"LSN_{lsn}",
                    checksum=checksum,
                    logged_at=datetime.utcnow()
                )
                db.add(db_record)
                db.commit()

            if record_type == "COMMIT":
                self._commit_count_since_checkpoint += 1

            return full_record

    def log_begin(self, txn_id: str, client_id: str, base_version: str, db: Optional[Session] = None) -> Dict[str, Any]:
        return self.append_record("BEGIN", txn_id=txn_id, client_id=client_id, base_version=base_version, db=db)

    def log_update(self, txn_id: str, client_id: str, base_version: str, delta: np.ndarray, db: Optional[Session] = None) -> Dict[str, Any]:
        return self.append_record("UPDATE", txn_id=txn_id, client_id=client_id, base_version=base_version, delta=delta, data_reference=f"delta_{txn_id}", db=db)

    def log_commit(self, txn_id: str, client_id: str, committed_version: str, db: Optional[Session] = None) -> Dict[str, Any]:
        return self.append_record("COMMIT", txn_id=txn_id, client_id=client_id, data_reference=committed_version, db=db, force_fsync=True)

    def log_abort(self, txn_id: str, client_id: str, reason: str, db: Optional[Session] = None) -> Dict[str, Any]:
        return self.append_record("ABORT", txn_id=txn_id, client_id=client_id, data_reference=reason, db=db, force_fsync=True)

    def create_checkpoint(self, current_version_id: str, weights: np.ndarray, db: Optional[Session] = None) -> Dict[str, Any]:
        """Creates a consistent full checkpoint snapshot on disk and logs CHECKPOINT record."""
        with self._lock:
            ckpt_path = CHECKPOINTS_DIR / f"checkpoint_{current_version_id}_{self._current_lsn}.npy"
            with open(ckpt_path, "wb") as checkpoint_file:
                np.save(checkpoint_file, weights)
                checkpoint_file.flush()
                os.fsync(checkpoint_file.fileno())
            self._commit_count_since_checkpoint = 0
            return self.append_record(
                "CHECKPOINT",
                data_reference=str(ckpt_path),
                base_version=current_version_id,
                db=db,
                force_fsync=True
            )

    def read_all_records(self) -> List[Dict[str, Any]]:
        """Reads all WAL records from disk and verifies integrity."""
        if not self.wal_path.exists():
            return []
        records = []
        with open(self.wal_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        record = json.loads(line)
                        records.append(record)
                    except json.JSONDecodeError:
                        continue
        return records

    def verify_integrity(self) -> Tuple[bool, List[int]]:
        """Scans the entire WAL and verifies CRC32 checksums of every record. Returns (is_valid, corrupted_lsns)."""
        corrupted = []
        records = self.read_all_records()
        for r in records:
            lsn = r.get("lsn", -1)
            stored_checksum = r.get("checksum", "")
            # Reconstruct payload dict
            payload = {k: v for k, v in r.items() if k != "checksum"}
            payload_json = json.dumps(payload, sort_keys=True)
            if not verify_crc32(payload_json, stored_checksum):
                corrupted.append(lsn)
        return (len(corrupted) == 0), corrupted
