"""
Master Automated Test Suite for All 12 Required Specification Scenarios.
Directly implements Section 10 of the Project Implementation Specification:
1. Multiple clients submitting simultaneously.
2. Two transactions using the same snapshot.
3. Stale update rejection.
4. Priority scheduling and starvation prevention.
5. WAL persistence before commit.
6. Crash during an incomplete transaction.
7. Recovery of committed transactions.
8. Selective rollback of a malicious contribution.
9. Garbage collection with active snapshots.
10. Differential log reconstruction.
11. Corrupted WAL record detection.
12. Conflict prediction versus actual conflicts.
"""
import concurrent.futures
import json
from datetime import datetime
from pathlib import Path
import numpy as np
import pytest

from app.db.session import SessionLocal, init_db
from app.db.init_data import seed_system
from app.db.models import (
    Transaction, ModelVersion, ModelContribution, ScheduleEntry,
    ConflictPrediction, RollbackEvent, WALRecord, Validation
)
from app.engine.coordinator import DBMSTransactionCoordinator

@pytest.fixture
def test_env():
    init_db()
    db = SessionLocal()
    # Clean operational tables for pure isolation
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

# SCENARIO 1: Multiple clients submitting simultaneously
def test_scenario_1_multiple_clients_submitting_simultaneously(test_env):
    coord, db = test_env
    vid, base_w = coord.get_client_snapshot("bank_a", db)

    def submit_task(client_id, val):
        local_db = SessionLocal()
        try:
            delta = np.ones_like(base_w) * val
            return coord.submit_model_update(client_id, vid, delta, local_db)
        finally:
            local_db.close()

    # Submit concurrently using ThreadPoolExecutor
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        f1 = executor.submit(submit_task, "bank_a", 0.01)
        f2 = executor.submit(submit_task, "bank_b", 0.02)
        f3 = executor.submit(submit_task, "bank_d", 0.015)
        results = [f1.result(), f2.result(), f3.result()]

    # Concurrency control ensures atomic commits without silent lost overwrites
    statuses = [r["status"] for r in results]
    assert "COMMITTED" in statuses
    # Global version advanced monotonically
    assert coord.mvcc.current_version_number >= 1
    assert coord.scheduler.size() == 0
    assert db.query(ScheduleEntry).filter(ScheduleEntry.queue_status != "DEQUEUED").count() == 0

# SCENARIO 2: Two transactions using the same snapshot
def test_scenario_2_two_transactions_using_same_snapshot(test_env):
    coord, db = test_env
    # Both Bank A and Bank B read snapshot V0
    vid_a, w_a = coord.get_client_snapshot("bank_a", db)
    vid_b, w_b = coord.get_client_snapshot("bank_b", db)
    assert vid_a == vid_b

    # Bank A commits first
    delta_a = np.ones_like(w_a) * 0.01
    res_a = coord.submit_model_update("bank_a", vid_a, delta_a, db)
    assert res_a["status"] == "COMMITTED"

    # Bank B now submits based on the same snapshot (now stale by 1)
    delta_b = np.ones_like(w_b) * 0.01
    res_b = coord.submit_model_update("bank_b", vid_b, delta_b, db)
    assert res_b["staleness"] == 1
    # Adaptive staleness allows small aligned staleness
    assert res_b["status"] == "COMMITTED"

# SCENARIO 3: Stale update rejection
def test_scenario_3_stale_update_rejection(test_env):
    coord, db = test_env
    w = coord.mvcc.get_version_weights("v0")

    # Advance versions past max allowance (e.g. 7 versions ahead)
    for i in range(7):
        coord.mvcc.create_version(coord.mvcc.current_version_id, w + 0.001 * (i+1), 0.5, 0.9, db)

    # Client submits update against V0 (staleness 7 > max_allowance 6)
    delta = np.ones_like(w) * 0.02
    res = coord.submit_model_update("bank_e", "v0", delta, db)
    assert res["status"] == "ABORTED"
    assert res["validation_result"].startswith("REJECTED_")

# SCENARIO 4: Priority scheduling and starvation prevention
def test_scenario_4_priority_scheduling_and_starvation_prevention(test_env):
    coord, db = test_env
    # Slow client enqueued with initial staleness
    tx_slow = Transaction(
        transaction_id="tx_sched_slow",
        client_id="bank_e",
        base_version_id="v0",
        status="PENDING",
        staleness=2,
        priority_score=1.0,
        submitted_at=datetime.utcnow()
    )
    # Fast client enqueued with fresh snapshot
    tx_fast = Transaction(
        transaction_id="tx_sched_fast",
        client_id="bank_a",
        base_version_id="v0",
        status="PENDING",
        staleness=0,
        priority_score=1.0,
        submitted_at=datetime.utcnow()
    )
    db.add(tx_slow)
    db.add(tx_fast)
    db.commit()

    item_slow = coord.scheduler.enqueue("tx_sched_slow", "bank_e", "v0", np.zeros(10), staleness=2, db=db)
    # Simulate aging: slow client has been waiting for 15 seconds
    item_slow.enqueued_at -= 15.0

    item_fast = coord.scheduler.enqueue("tx_sched_fast", "bank_a", "v0", np.zeros(10), staleness=0, db=db)

    # Aging elevates slow client's priority score, preventing starvation
    selected = coord.scheduler.get_next(db=db)
    assert selected.transaction_id == "tx_sched_slow"

# SCENARIO 5: WAL persistence before commit
def test_scenario_5_wal_persistence_before_commit(test_env):
    coord, db = test_env
    vid, w = coord.get_client_snapshot("bank_a", db)
    delta = np.ones_like(w) * 0.01

    res = coord.submit_model_update("bank_a", vid, delta, db)
    assert res["status"] == "COMMITTED"
    txn_id = res["transaction_id"]

    # Verify physical file on disk contains the commit record with valid checksum
    records = coord.wal.read_all_records()
    txn_wal_records = [r for r in records if r.get("transaction_id") == txn_id]
    types = [r["record_type"] for r in txn_wal_records]
    assert "BEGIN" in types
    assert "UPDATE" in types
    assert "COMMIT" in types

# SCENARIO 6: Crash during an incomplete transaction
def test_scenario_6_crash_during_incomplete_transaction(test_env):
    coord, db = test_env
    w = coord.mvcc.get_version_weights("v0")

    # Incomplete transaction: BEGIN & UPDATE written, but server crashes before COMMIT
    tx_inc = Transaction(
        transaction_id="tx_incomplete_crash",
        client_id="bank_b",
        base_version_id="v0",
        status="VALIDATING",
        staleness=0,
        priority_score=1.0,
        submitted_at=datetime.utcnow()
    )
    db.add(tx_inc)
    db.commit()
    coord.wal.log_begin("tx_incomplete_crash", "bank_b", "v0", db=db)
    coord.wal.log_update("tx_incomplete_crash", "bank_b", "v0", np.ones_like(w) * 0.5, db=db)

    # Simulate crash
    coord.recovery.simulate_crash()
    assert coord.recovery.is_crashed is True

    # Recovery
    stats = coord.recovery.restart_and_recover(db)
    assert stats["incomplete_txns_discarded"] >= 1

    # Check incomplete transaction status in DB is now ABORTED
    db.expire_all()
    recovered_tx = db.query(Transaction).filter(Transaction.transaction_id == "tx_incomplete_crash").first()
    assert recovered_tx.status == "ABORTED"

# SCENARIO 7: Recovery of committed transactions
def test_scenario_7_recovery_of_committed_transactions(test_env):
    coord, db = test_env
    vid, w = coord.get_client_snapshot("bank_a", db)
    res = coord.submit_model_update("bank_a", vid, np.ones_like(w) * 0.03, db)
    assert res["status"] == "COMMITTED"
    committed_id = res["transaction_id"]

    # Simulate crash & restart
    coord.recovery.simulate_crash()
    stats = coord.recovery.restart_and_recover(db)

    assert stats["status"] == "RECOVERY_COMPLETE"
    assert committed_id in stats["replayed_transactions"]

# SCENARIO 8: Selective rollback of a malicious contribution
def test_scenario_8_selective_rollback_of_a_malicious_contribution(test_env):
    coord, db = test_env
    vid, w = coord.get_client_snapshot("bank_c", db)

    # Commit poisoned update
    delta_poison = np.ones_like(w) * 4.5
    res = coord.submit_model_update("bank_c", vid, delta_poison, db)
    assert res["status"] == "COMMITTED"
    poison_id = res["transaction_id"]

    # Execute Selective Rollback
    rb_res = coord.rollback.rollback_transaction(
        target_transaction_id=poison_id,
        reason="Byzantine poisoning detected from Bank C",
        db=db
    )
    assert rb_res["status"] == "ROLLBACK_SUCCESS"
    assert poison_id in rb_res["skipped_transactions"]

    # Relational catalog contribution is disabled
    contrib = db.query(ModelContribution).filter(ModelContribution.transaction_id == poison_id).first()
    assert contrib.is_active is False

# SCENARIO 9: Garbage collection with active snapshots
def test_scenario_9_garbage_collection_with_active_snapshots(test_env):
    coord, db = test_env
    # Bank E pins current version
    pinned_vid, _ = coord.get_client_snapshot("bank_e", db)

    # Create several subsequent versions
    w = coord.mvcc.get_version_weights(coord.mvcc.current_version_id)
    for i in range(4):
        coord.mvcc.create_version(coord.mvcc.current_version_id, w + 0.001 * (i+1), 0.5, 0.9, db)

    # Vacuum
    gc_stats = coord.gc.run_garbage_collection(db, keep_latest_n=1)

    # Pinned version held by Bank E MUST be preserved
    assert pinned_vid in gc_stats["protected_versions"]
    assert pinned_vid not in gc_stats["pruned_versions"]

# SCENARIO 10: Differential log reconstruction
def test_scenario_10_differential_log_reconstruction(test_env):
    coord, _ = test_env
    w0 = np.array([0.5, -0.2, 0.1, 0.8], dtype=np.float32)
    delta_1 = np.array([0.02, 0.01, -0.01, 0.00], dtype=np.float32)
    delta_2 = np.array([-0.01, 0.03, 0.00, 0.02], dtype=np.float32)

    expected = w0 + delta_1 + delta_2
    reconstructed = coord.differential.reconstruct_model_from_deltas(w0, [delta_1, delta_2])
    np.testing.assert_allclose(expected, reconstructed, atol=1e-5)

# SCENARIO 11: Corrupted WAL record detection
def test_scenario_11_corrupted_wal_record_detection(test_env):
    coord, db = test_env
    wal_file = Path(coord.wal.wal_path)

    # Insert transaction row in catalog to satisfy FK constraint
    txn = Transaction(
        transaction_id="tx_tamper_test",
        client_id="bank_a",
        base_version_id="v0",
        status="PENDING",
        staleness=0,
        priority_score=1.0,
        submitted_at=datetime.utcnow()
    )
    db.add(txn)
    db.commit()

    # Read records, alter one byte, verify detection
    coord.wal.log_begin("tx_tamper_test", "bank_a", "v0", db=db)
    records = coord.wal.read_all_records()

    # Tamper with the last line on disk
    with open(wal_file, "r") as f:
        original_lines = f.readlines()

    tampered = json.loads(original_lines[-1])
    tampered["transaction_id"] = "TAMPERED_ID"
    corrupted_lines = list(original_lines)
    corrupted_lines[-1] = json.dumps(tampered) + "\n"

    with open(wal_file, "w") as f:
        f.writelines(corrupted_lines)

    is_valid, corrupted = coord.wal.verify_integrity()
    assert is_valid is False
    assert len(corrupted) >= 1

    # Restore uncorrupted WAL file for subsequent tests
    with open(wal_file, "w") as f:
        f.writelines(original_lines)

# SCENARIO 12: Conflict prediction versus actual conflicts
def test_scenario_12_conflict_prediction_vs_actual_conflicts(test_env):
    coord, db = test_env

    # Insert transaction rows for FK integrity
    t_low = Transaction(
        transaction_id="tx_test_pred_low",
        client_id="bank_a",
        base_version_id="v0",
        status="PENDING",
        staleness=0,
        priority_score=1.0,
        submitted_at=datetime.utcnow()
    )
    t_high = Transaction(
        transaction_id="tx_test_pred_high",
        client_id="bank_c",
        base_version_id="v0",
        status="PENDING",
        staleness=5,
        priority_score=1.0,
        submitted_at=datetime.utcnow()
    )
    db.add(t_low)
    db.add(t_high)
    db.commit()

    # Low-risk prediction on fresh update
    pred_low = coord.predictor.predict_risk(
        txn_id="tx_test_pred_low",
        client_id="bank_a",
        staleness=0,
        client_delta=np.zeros(10),
        current_queue_depth=0,
        db=db
    )
    assert pred_low["risk_category"] == "LOW"

    # High-risk prediction on high staleness and large norm
    pred_high = coord.predictor.predict_risk(
        txn_id="tx_test_pred_high",
        client_id="bank_c",
        staleness=5,
        client_delta=np.ones(10) * 2.0,
        current_queue_depth=5,
        db=db
    )
    assert pred_high["risk_category"] in ["MEDIUM", "HIGH"]
    assert "advisory" in pred_high["note"].lower()


def test_concurrent_commits_rebase_each_update_on_latest_head(test_env):
    """Accepted same-snapshot updates must all be reflected in the final head."""
    coord, _ = test_env
    base_vid = coord.mvcc.current_version_id
    initial_head = coord.mvcc.get_version_weights(base_vid).copy()
    updates = {
        "bank_a": np.full_like(initial_head, 0.001),
        "bank_b": np.full_like(initial_head, 0.002),
        "bank_d": np.full_like(initial_head, 0.003),
    }

    def submit(client_id, delta):
        local_db = SessionLocal()
        try:
            return coord.submit_model_update(client_id, base_vid, delta, local_db)
        finally:
            local_db.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(updates)) as pool:
        results = list(pool.map(lambda item: submit(*item), updates.items()))

    assert all(result["status"] == "COMMITTED" for result in results)
    expected = initial_head.copy()
    for (client_id, delta), result in zip(updates.items(), results):
        expected += delta * result["scaling_factor"]
    actual = coord.mvcc.get_version_weights(coord.mvcc.current_version_id)
    # Each commit rounds the accumulated vector to float32, so allow only the
    # small bounded rounding difference from summing the deltas in one pass.
    np.testing.assert_allclose(actual, expected, rtol=1e-5, atol=3e-6)


def test_recovery_publishes_durable_commit_missing_from_catalog(test_env):
    """Redo completes a COMMIT whose process died before publishing its version."""
    coord, db = test_env
    base_vid = coord.mvcc.current_version_id
    base_weights = coord.mvcc.get_version_weights(base_vid).copy()
    txn_id = "tx_durable_before_publish"
    committed_vid = f"v{coord.mvcc.current_version_number + 1}"
    delta = np.full_like(base_weights, 0.0005)
    db.add(Transaction(
        transaction_id=txn_id,
        client_id="bank_a",
        base_version_id=base_vid,
        status="VALIDATING",
        staleness=0,
        priority_score=1.0,
        submitted_at=datetime.utcnow()
    ))
    db.commit()
    coord.wal.log_begin(txn_id, "bank_a", base_vid, db=db)
    coord.wal.log_update(txn_id, "bank_a", base_vid, delta, db=db)
    coord.wal.log_commit(txn_id, "bank_a", committed_vid, db=db)

    coord.recovery.simulate_crash()
    recovery = coord.recovery.restart_and_recover(db)

    db.expire_all()
    recovered_tx = db.query(Transaction).filter_by(transaction_id=txn_id).one()
    recovered_version = db.query(ModelVersion).filter_by(version_id=committed_vid).one()
    assert recovered_tx.status == "COMMITTED"
    assert recovered_tx.committed_version_id == committed_vid
    assert recovered_version.parent_version_id is not None
    assert recovery["status"] == "RECOVERY_COMPLETE"
