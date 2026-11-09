"""
Unit & Integration Tests for API Route Handlers.
Directly exercises route handlers, database session dependencies, and coordinator logic.
"""
import pytest
from app.db.session import SessionLocal, init_db
from app.db.init_data import seed_system
from app.engine import coordinator, simulator
from app.main import root
from app.api.fl_routes import get_clients, simulation_step, get_model_snapshot, control_client, ClientControlRequest
from app.api.transaction_routes import list_transactions, get_scheduler_queue
from app.api.mvcc_routes import get_version_lineage, get_active_snapshots
from app.api.wal_routes import get_wal_records, verify_wal_integrity
from app.api.optimization_routes import get_staleness_config, update_staleness_config, StalenessConfigRequest, get_differential_metrics
from app.api.analytics_routes import get_dashboard_overview, export_experiment_results_csv, compare_with_last_writer_wins

@pytest.fixture
def db():
    init_db()
    session = SessionLocal()
    seed_system(session)
    coordinator.initialize(session)
    yield session
    session.close()

def test_root():
    res = root()
    assert res["status"] == "ONLINE"
    assert "current_version" in res

def test_fl_clients_and_control(db):
    clients = get_clients(db=db)
    assert len(clients) == 5
    client_ids = [c["client_id"] for c in clients]
    assert "bank_a" in client_ids
    assert "bank_e" in client_ids

    # Test client control (pause and change delay)
    updated = control_client("bank_b", ClientControlRequest(status="PAUSED", delay_seconds=1.5), db=db)
    assert updated["status"] == "PAUSED"
    assert updated["delay_seconds"] == 1.5

    # Resume
    control_client("bank_b", ClientControlRequest(status="ACTIVE", delay_seconds=0.4), db=db)

def test_snapshot_and_simulation_step(db):
    snap = get_model_snapshot("bank_a", db=db)
    assert snap["snapshot_version_id"] == coordinator.mvcc.current_version_id
    assert "weights_b64" in snap

    # Step simulation
    step_res = simulation_step("bank_a", db=db)
    assert len(step_res["results"]) >= 1
    assert step_res["results"][0]["status"] == "COMMITTED"


def test_all_bank_simulation_runs_clients_concurrently(db):
    result = simulation_step(db=db)
    assert len(result["results"]) == 5
    assert all(item["status"] in {"COMMITTED", "ABORTED"} for item in result["results"])

def test_transactions_and_mvcc_views(db):
    # Ensure at least one transaction exists
    simulation_step("bank_a", db=db)

    tx_list = list_transactions(status="ALL", client_id="ALL", limit=10, offset=0, db=db)
    assert tx_list["total"] >= 1
    assert len(tx_list["transactions"]) >= 1

    versions = get_version_lineage()
    assert len(versions) >= 1

    snapshots = get_active_snapshots()
    assert isinstance(snapshots, dict)

def test_wal_records_and_integrity():
    wal_res = get_wal_records(limit=20, offset=0)
    assert wal_res["total"] >= 1

    integ = verify_wal_integrity()
    assert integ["is_valid"] is True

def test_optimization_and_analytics(db):
    # Ensure at least one transaction exists
    simulation_step("bank_a", db=db)

    # Staleness config
    cfg = get_staleness_config()
    assert "base_threshold" in cfg

    upd = update_staleness_config(StalenessConfigRequest(base_threshold=4, max_allowance=7))
    assert upd["base_threshold"] == 4

    # Differential metrics
    diff = get_differential_metrics()
    assert "differential_logging_bytes" in diff

    # Analytics Overview
    overview = get_dashboard_overview(db=db)
    assert overview["total_clients"] == 5
    assert overview["total_transactions"] >= 1

    baseline = compare_with_last_writer_wins(db=db)
    assert baseline["status"] == "COMPARISON_READY"
    assert baseline["replayed_contributions"] >= 1
    assert "not an end-to-end performance benchmark" in baseline["protocol"]

    # CSV Export
    csv_resp = export_experiment_results_csv(db=db)
    assert "TRANSACTIONS AUDIT LOG" in csv_resp.body.decode("utf-8")
