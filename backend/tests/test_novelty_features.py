"""
Phase 5 Unit Tests: Six Novelty Features
1. Priority Scheduling & Starvation Prevention
2. Selective Rollback of Malicious Contribution
3. Snapshot-Aware Adaptive Garbage Collection
4. Transaction Conflict Prediction
5. Differential WAL Storage & Reconstruction
"""
import time
import pytest
import numpy as np
from datetime import datetime
from app.db.session import SessionLocal, init_db
from app.db.models import Transaction, ModelVersion, ModelContribution, RollbackEvent, WALRecord, Client
from app.engine.coordinator import DBMSTransactionCoordinator

@pytest.fixture
def coordinator_db():
    init_db()
    db = SessionLocal()
    # Clean operational tables for clean test isolation
    from app.db.models import ScheduleEntry, ConflictPrediction, RollbackEvent, ModelContribution, WALRecord, Validation, Transaction
    db.query(ScheduleEntry).delete()
    db.query(ConflictPrediction).delete()
    db.query(RollbackEvent).delete()
    db.query(ModelContribution).delete()
    db.query(WALRecord).delete()
    db.query(Validation).delete()
    db.query(Transaction).delete()
    db.commit()

    coord = DBMSTransactionCoordinator()
    coord.initialize(db)
    yield coord, db
    db.close()

def test_priority_scheduling_starvation_prevention(coordinator_db):
    coord, db = coordinator_db
    
    # 0. Insert transaction records into catalog
    tx_e = Transaction(
        transaction_id="tx_slow_e",
        client_id="bank_e",
        base_version_id="v0",
        status="PENDING",
        staleness=2,
        priority_score=1.0,
        submitted_at=datetime.utcnow()
    )
    tx_a = Transaction(
        transaction_id="tx_fast_a",
        client_id="bank_a",
        base_version_id="v0",
        status="PENDING",
        staleness=0,
        priority_score=1.0,
        submitted_at=datetime.utcnow()
    )
    db.add(tx_e)
    db.add(tx_a)
    db.commit()

    # Client E (slow bank) enqueued first with staleness 2
    item_e = coord.scheduler.enqueue("tx_slow_e", "bank_e", "v0", np.zeros(10), staleness=2, db=db)
    
    # Artificially age item_e's waiting time
    item_e.enqueued_at -= 10.0  # waited 10 seconds
    
    # Client A (fast bank) enqueued recently with staleness 0
    item_a = coord.scheduler.enqueue("tx_fast_a", "bank_a", "v0", np.zeros(10), staleness=0, db=db)
    
    # Slower transaction should achieve higher priority due to aging boost despite staleness
    next_up = coord.scheduler.get_next(db=db)
    assert next_up.transaction_id == "tx_slow_e"

def test_selective_rollback_of_poisoned_update(coordinator_db):
    coord, db = coordinator_db
    
    # 1. Commit valid transaction from Bank A
    vid, base_w = coord.get_client_snapshot("bank_a", db)
    delta_valid_1 = np.ones_like(base_w) * 0.02
    res_1 = coord.submit_model_update("bank_a", vid, delta_valid_1, db)
    assert res_1["status"] == "COMMITTED"
    
    # 2. Commit poisoned transaction from Bank C (simulated attacker)
    vid_2, _ = coord.get_client_snapshot("bank_c", db)
    delta_poisoned = np.ones_like(base_w) * 5.0  # extreme surge
    res_poison = coord.submit_model_update("bank_c", vid_2, delta_poisoned, db)
    assert res_poison["status"] == "COMMITTED"
    poisoned_tx_id = res_poison["transaction_id"]
    
    # 3. Commit another valid transaction from Bank B
    vid_3, _ = coord.get_client_snapshot("bank_b", db)
    delta_valid_2 = np.ones_like(base_w) * 0.01
    res_3 = coord.submit_model_update("bank_b", vid_3, delta_valid_2, db)
    assert res_3["status"] == "COMMITTED"
    
    # 4. Trigger Selective Rollback of the poisoned transaction
    rb_res = coord.rollback.rollback_transaction(
        target_transaction_id=poisoned_tx_id,
        reason="Detected adversarial parameter surge in Bank C contribution",
        db=db
    )
    
    assert rb_res["status"] == "ROLLBACK_SUCCESS"
    assert poisoned_tx_id in rb_res["skipped_transactions"]
    assert rb_res["replayed_transactions_count"] >= 2
    
    # Verify poisoned transaction contribution is marked inactive
    poison_contrib = db.query(ModelContribution).filter(ModelContribution.transaction_id == poisoned_tx_id).first()
    assert poison_contrib.is_active is False
    
    # Verify target transaction is marked ABORTED
    poison_txn = db.query(Transaction).filter(Transaction.transaction_id == poisoned_tx_id).first()
    assert poison_txn.status == "ABORTED"

def test_garbage_collection_with_active_snapshot(coordinator_db):
    coord, db = coordinator_db
    
    # Bank E pins current version
    pinned_vid, _ = coord.get_client_snapshot("bank_e", db)
    
    # Generate multiple versions
    w = coord.mvcc.get_version_weights(coord.mvcc.current_version_id)
    for i in range(5):
        coord.mvcc.create_version(coord.mvcc.current_version_id, w + 0.001 * (i+1), 0.5, 0.9, db)
        
    gc_stats = coord.gc.run_garbage_collection(db, keep_latest_n=2)
    
    # Verify that pinned_vid was NOT pruned
    assert pinned_vid in gc_stats["protected_versions"]
    assert pinned_vid not in gc_stats["pruned_versions"]

def test_differential_wal_reconstruction(coordinator_db):
    coord, _ = coordinator_db
    
    base_w = np.array([0.1, 0.2, 0.3, 0.4, 0.5], dtype=np.float32)
    d1 = np.array([0.01, 0.00, -0.02, 0.05, 0.00], dtype=np.float32)
    d2 = np.array([-0.05, 0.03, 0.01, -0.01, 0.02], dtype=np.float32)
    
    # Sequential updates
    target_w = base_w + d1 + d2
    
    # Reconstruct from delta chain
    reconstructed = coord.differential.reconstruct_model_from_deltas(base_w, [d1, d2])
    np.testing.assert_allclose(target_w, reconstructed, atol=1e-5)
    
    # Test storage metrics
    coord.differential.record_storage_metrics(target_w, d1)
    metrics = coord.differential.get_comparison_metrics()
    assert metrics["differential_logging_bytes"] > 0
    assert metrics["storage_saved_mb"] >= 0.0
