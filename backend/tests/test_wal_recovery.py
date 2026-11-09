"""
Phase 3 Unit Tests: Custom Persistent WAL and ARIES Crash Recovery
Verifies durable append-only logging, CRC32 corruption detection, checkpoints, and Redo/Undo recovery.
"""
import json
import pytest
import numpy as np
from datetime import datetime
from pathlib import Path
from app.db.session import SessionLocal, init_db
from app.db.models import Transaction, ModelVersion, WALRecord
from app.engine.mvcc import MVCCVersionManager
from app.engine.wal import WALManager
from app.engine.recovery import CrashRecoveryManager
from app.config import DATA_DIR

from tests.conftest import clean_operational_tables

@pytest.fixture
def clean_wal(tmp_path):
    test_wal_file = tmp_path / "test.wal"
    wal_mgr = WALManager(wal_path=str(test_wal_file))
    return wal_mgr, test_wal_file

@pytest.fixture
def db_session():
    init_db()
    db = SessionLocal()
    clean_operational_tables(db)
    yield db
    db.close()

def test_wal_persistence_and_checksum(clean_wal, db_session):
    wal_mgr, wal_file = clean_wal
    
    # 0. Create transaction row in catalog
    txn = Transaction(
        transaction_id="tx_wal_1",
        client_id="bank_a",
        base_version_id="v0",
        status="PENDING",
        staleness=0,
        priority_score=1.0,
        submitted_at=datetime.utcnow()
    )
    db_session.add(txn)
    db_session.commit()

    # 1. Log BEGIN
    rec_begin = wal_mgr.log_begin("tx_wal_1", "bank_a", "v0", db=db_session)
    assert rec_begin["lsn"] == 1
    assert "checksum" in rec_begin
    
    # 2. Log UPDATE
    dummy_delta = np.array([0.1, 0.2, 0.3], dtype=np.float32)
    rec_update = wal_mgr.log_update("tx_wal_1", "bank_a", "v0", dummy_delta, db=db_session)
    assert rec_update["lsn"] == 2
    
    # 3. Log COMMIT
    rec_commit = wal_mgr.log_commit("tx_wal_1", "bank_a", "v1", db=db_session)
    assert rec_commit["lsn"] == 3
    
    # 4. Check physical disk contents
    assert wal_file.exists()
    records = wal_mgr.read_all_records()
    assert len(records) == 3
    
    # 5. Integrity verification
    is_valid, corrupted = wal_mgr.verify_integrity()
    assert is_valid is True
    assert len(corrupted) == 0


def test_checkpoint_creation_appends_record_without_deadlock(tmp_path):
    wal_mgr = WALManager(wal_path=str(tmp_path / "checkpoint.wal"))
    checkpoint = wal_mgr.create_checkpoint("v0", np.zeros(4, dtype=np.float32))
    assert checkpoint["record_type"] == "CHECKPOINT"
    assert Path(checkpoint["data_reference"]).exists()

def test_corrupted_wal_detection(clean_wal):
    wal_mgr, wal_file = clean_wal
    
    wal_mgr.log_begin("tx_1", "bank_a", "v0")
    wal_mgr.log_commit("tx_1", "bank_a", "v1")
    
    # Tamper with the physical file (corrupting a record)
    with open(wal_file, "r") as f:
        lines = f.readlines()
    
    # Modify data payload without updating checksum
    corrupted_data = json.loads(lines[0])
    corrupted_data["transaction_id"] = "tx_TAMPERED"
    lines[0] = json.dumps(corrupted_data) + "\n"
    
    with open(wal_file, "w") as f:
        f.writelines(lines)
        
    is_valid, corrupted = wal_mgr.verify_integrity()
    assert is_valid is False
    assert 1 in corrupted  # LSN 1 detected as corrupted

def test_crash_recovery_redo_and_undo(clean_wal, db_session):
    wal_mgr, wal_file = clean_wal
    mvcc = MVCCVersionManager()
    mvcc.load_from_db(db_session)
    recovery_mgr = CrashRecoveryManager(wal_mgr, mvcc)
    
    base_w = mvcc.get_version_weights("v0")
    delta_committed = np.ones_like(base_w) * 0.05
    delta_uncommitted = np.ones_like(base_w) * 0.99
    
    # 1. Fully committed transaction tx_c
    tx_c = Transaction(
        transaction_id="tx_c",
        client_id="bank_a",
        base_version_id="v0",
        status="COMMITTED",
        staleness=0,
        priority_score=1.0,
        submitted_at=datetime.utcnow()
    )
    db_session.add(tx_c)
    db_session.commit()
    wal_mgr.log_begin("tx_c", "bank_a", "v0", db=db_session)
    wal_mgr.log_update("tx_c", "bank_a", "v0", delta_committed, db=db_session)
    wal_mgr.log_commit("tx_c", "bank_a", "v1", db=db_session)
    
    # 2. Incomplete transaction tx_inc (in-flight when crash happens)
    tx_inc = Transaction(
        transaction_id="tx_inc",
        client_id="bank_b",
        base_version_id="v0",
        status="VALIDATING",
        staleness=0,
        priority_score=1.0,
        submitted_at=datetime.utcnow()
    )
    db_session.add(tx_inc)
    db_session.commit()
    wal_mgr.log_begin("tx_inc", "bank_b", "v0", db=db_session)
    wal_mgr.log_update("tx_inc", "bank_b", "v0", delta_uncommitted, db=db_session)
    # Notice: NO COMMIT logged for tx_inc!
    
    # 3. Simulate Server Crash
    recovery_mgr.simulate_crash()
    assert recovery_mgr.is_crashed is True
    
    # 4. Restart and Recover
    stats = recovery_mgr.restart_and_recover(db_session)
    
    assert stats["status"] == "RECOVERY_COMPLETE"
    assert stats["committed_txns_recovered"] == 1
    assert stats["incomplete_txns_discarded"] == 1
    assert "tx_c" in stats["replayed_transactions"]
    assert "tx_inc" not in stats["replayed_transactions"]
    
    # Verify uncommitted transaction is marked ABORTED in database
    db_session.expire_all()
    recovered_tx_inc = db_session.query(Transaction).filter(Transaction.transaction_id == "tx_inc").first()
    assert recovered_tx_inc.status == "ABORTED"
