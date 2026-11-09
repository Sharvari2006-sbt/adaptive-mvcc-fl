"""
Phase 2 Unit Tests: Custom MVCC and OCC Validation
Verifies snapshot isolation, version progression, staleness bounds, and write-write conflict handling.
"""
import pytest
import numpy as np
from datetime import datetime
from app.db.session import SessionLocal, init_db
from app.db.models import Client, ModelVersion, Transaction, Validation
from app.engine.mvcc import MVCCVersionManager
from app.engine.staleness import AdaptiveStalenessManager
from app.engine.occ import OCCValidationEngine
from app.fl.model import get_initial_weights

from tests.conftest import clean_operational_tables

@pytest.fixture
def test_db():
    init_db()
    db = SessionLocal()
    clean_operational_tables(db)
    yield db
    db.close()

@pytest.fixture
def engine_setup(test_db):
    mvcc = MVCCVersionManager()
    mvcc.load_from_db(test_db)
    staleness_mgr = AdaptiveStalenessManager(base_threshold=2, max_allowance=4, cosine_threshold=0.3)
    occ = OCCValidationEngine(mvcc, staleness_mgr, conflict_norm_threshold=0.7)
    return mvcc, staleness_mgr, occ

def test_snapshot_isolation(engine_setup, test_db):
    mvcc, _, _ = engine_setup
    
    # Bank A reads snapshot
    vid_a, weights_a = mvcc.get_snapshot("bank_a", db=test_db)
    assert vid_a == mvcc.current_version_id
    assert mvcc._active_readers[vid_a] >= 1
    
    # Bank B reads snapshot
    vid_b, weights_b = mvcc.get_snapshot("bank_b", db=test_db)
    assert vid_b == vid_a
    assert mvcc._active_readers[vid_a] >= 2
    
    # Release snapshot
    mvcc.release_snapshot("bank_a", db=test_db)
    assert mvcc._active_readers[vid_a] == 1
    mvcc.release_snapshot("bank_b", db=test_db)
    assert mvcc._active_readers[vid_a] == 0

def test_occ_fresh_commit(engine_setup, test_db):
    mvcc, staleness_mgr, occ = engine_setup
    
    vid, base_w = mvcc.get_snapshot("bank_a", db=test_db)
    delta = np.ones_like(base_w) * 0.01
    
    # Create txn in DB
    txn = Transaction(
        transaction_id="tx_test_1",
        client_id="bank_a",
        base_version_id=vid,
        status="VALIDATING",
        staleness=0,
        priority_score=1.0,
        submitted_at=datetime.utcnow()
    )
    test_db.add(txn)
    test_db.commit()
    
    # Validate
    is_valid, status, conflict_score, scale = occ.validate_transaction(
        txn.transaction_id, "bank_a", vid, delta, test_db
    )
    assert is_valid is True
    assert status == "PASSED"
    assert scale == 1.0

def test_stale_update_rejection(engine_setup, test_db):
    mvcc, staleness_mgr, occ = engine_setup
    
    # Current version is v0, advance versions artificially to v5 (staleness = 5 > max_allowance 4)
    w = mvcc.get_version_weights("v0")
    for i in range(1, 6):
        mvcc.create_version(f"v{i-1}", w + 0.001 * i, loss=0.5, accuracy=0.9, db=test_db)
        occ.record_committed_delta(i, np.ones_like(w) * 0.001)
        
    txn = Transaction(
        transaction_id="tx_stale_test",
        client_id="bank_e",
        base_version_id="v0",
        status="VALIDATING",
        staleness=5,
        priority_score=1.0,
        submitted_at=datetime.utcnow()
    )
    test_db.add(txn)
    test_db.commit()
    
    delta = np.ones_like(w) * 0.02
    is_valid, status, conflict_score, scale = occ.validate_transaction(
        txn.transaction_id, "bank_e", "v0", delta, test_db
    )
    assert is_valid is False
    assert status == "REJECTED_STALE"

def test_opposing_write_conflict(engine_setup, test_db):
    mvcc, staleness_mgr, occ = engine_setup
    
    # Capture base version right now
    base_vid = mvcc.current_version_id
    base_num = mvcc.current_version_number
    w = mvcc.get_version_weights(base_vid)

    # Create an intervening commit with delta = +0.1
    delta_intervening = np.ones_like(w) * 0.1
    new_v = mvcc.create_version(base_vid, w + delta_intervening, 0.4, 0.92, test_db)
    occ.record_committed_delta(mvcc.current_version_number, delta_intervening)
    
    # Now client submits update based on base_vid (staleness = 1 <= base_threshold 2), but with opposing vector: -0.1
    delta_opposing = -np.ones_like(w) * 0.1
    txn = Transaction(
        transaction_id="tx_conflict_test",
        client_id="bank_c",
        base_version_id=base_vid,
        status="VALIDATING",
        staleness=1,
        priority_score=1.0,
        submitted_at=datetime.utcnow()
    )
    test_db.add(txn)
    test_db.commit()
    
    is_valid, status, conflict_score, scale = occ.validate_transaction(
        txn.transaction_id, "bank_c", base_vid, delta_opposing, test_db
    )
    assert is_valid is False
    assert status == "REJECTED_CONFLICT"
