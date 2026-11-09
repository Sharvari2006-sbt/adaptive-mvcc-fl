"""
Federated Learning Client Communication & Simulation Endpoints.
Handles client snapshot requests, model update submissions, client controls,
and background asynchronous AFL execution.
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
import numpy as np
from concurrent.futures import ThreadPoolExecutor

from app.db.session import get_db
from app.db.models import Client, Transaction
from app.engine import coordinator, simulator
from app.utils.serialization import serialize_weights_to_base64, deserialize_weights_from_base64

router = APIRouter(prefix="/fl", tags=["Federated Learning"])

class ClientControlRequest(BaseModel):
    status: Optional[str] = None          # "ACTIVE", "PAUSED"
    delay_seconds: Optional[float] = None
    is_malicious: Optional[bool] = None
    force_outdated: Optional[bool] = None

class UpdateSubmissionRequest(BaseModel):
    client_id: str
    base_version_id: str
    delta_weights_b64: str

@router.get("/clients", response_model=List[Dict[str, Any]])
def get_clients(db: Session = Depends(get_db)):
    """Returns real-time status and telemetry for all 5 simulated bank clients."""
    return simulator.get_all_client_stats()

@router.post("/clients/{client_id}/control")
def control_client(client_id: str, payload: ClientControlRequest, db: Session = Depends(get_db)):
    """Updates client configuration: delay, pause/resume, malicious poisoning, or stale snapshot."""
    client = simulator.get_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail=f"Client {client_id} not found.")

    if payload.status is not None:
        simulator.set_status(client_id, payload.status)
        db_client = db.query(Client).filter(Client.client_id == client_id).first()
        if db_client:
            db_client.status = payload.status
            db.commit()

    if payload.delay_seconds is not None:
        simulator.set_delay(client_id, payload.delay_seconds)

    if payload.is_malicious is not None:
        simulator.set_malicious(client_id, payload.is_malicious)

    if payload.force_outdated is not None:
        simulator.set_outdated(client_id, payload.force_outdated)

    return {
        "client_id": client_id,
        "status": client.status,
        "delay_seconds": client.delay_seconds,
        "is_malicious": client.is_malicious,
        "force_outdated": client.force_outdated
    }

@router.get("/snapshot/{client_id}")
def get_model_snapshot(client_id: str, db: Session = Depends(get_db)):
    """
    Read Phase: Client requests model weights snapshot.
    Acquires MVCC snapshot pin.
    """
    client = simulator.get_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail=f"Client {client_id} not registered.")

    # Check if forced outdated simulation is enabled for this client
    if client.force_outdated:
        target_vid = "v0"
        weights = coordinator.mvcc.get_version_weights("v0")
    else:
        target_vid, weights = coordinator.get_client_snapshot(client_id, db=db)

    client.current_snapshot_vid = target_vid
    encoded = serialize_weights_to_base64(weights)

    return {
        "client_id": client_id,
        "snapshot_version_id": target_vid,
        "weights_b64": encoded,
        "parameters_count": int(weights.shape[0])
    }

@router.post("/submit-update")
def submit_model_update(payload: UpdateSubmissionRequest, db: Session = Depends(get_db)):
    """
    Write Phase: Receives client weight delta and submits to DBMS transaction manager.
    """
    client = simulator.get_client(payload.client_id)
    if not client:
        raise HTTPException(status_code=404, detail=f"Client {payload.client_id} not registered.")

    delta = deserialize_weights_from_base64(payload.delta_weights_b64)
    client.total_submissions += 1

    try:
        result = coordinator.submit_model_update(
            client_id=payload.client_id,
            base_version_id=payload.base_version_id,
            delta=delta,
            db=db
        )
        if result["status"] == "COMMITTED":
            client.successful_commits += 1
        else:
            client.aborted_txns += 1

        import datetime
        client.last_submitted_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        return result
    except Exception as e:
        client.aborted_txns += 1
        raise HTTPException(status_code=500, detail=str(e))

def _run_single_client_round(client_id: str, db: Session):
    """Executes a single end-to-end AFL training and transaction submission step for one bank."""
    client = simulator.get_client(client_id)
    if not client or client.status != "ACTIVE":
        return None

    # 1. Read Snapshot
    if client.force_outdated:
        base_vid = "v0"
        base_w = coordinator.mvcc.get_version_weights("v0")
    else:
        base_vid, base_w = coordinator.get_client_snapshot(client_id, db=db)

    client.current_snapshot_vid = base_vid

    # 2. Local Training on Bank's Private Data
    delta, loss, acc = client.train_local_step(base_w, epochs=1)

    # 3. Submit Transaction to DBMS Engine
    client.total_submissions += 1
    result = coordinator.submit_model_update(
        client_id=client_id,
        base_version_id=base_vid,
        delta=delta,
        db=db
    )

    if result["status"] == "COMMITTED":
        client.successful_commits += 1
    else:
        client.aborted_txns += 1

    import datetime
    client.last_submitted_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    return result

@router.post("/simulation/step")
def simulation_step(client_id: Optional[str] = None, db: Session = Depends(get_db)):
    """
    Manually triggers one round of federated training for a specific bank or all active banks.
    Ideal for step-by-step professor demonstrations!
    """
    if client_id:
        res = _run_single_client_round(client_id, db)
        return {"results": [res] if res else []}
    
    active_ids = [cid for cid, client in simulator.clients.items() if client.status == "ACTIVE"]
    if not active_ids:
        return {"results": []}

    # Each simulated bank has an independent DB session and trains from its
    # own snapshot concurrently. The coordinator serializes only validation
    # and commit, which preserves atomicity while modeling asynchronous clients.
    with ThreadPoolExecutor(max_workers=len(active_ids)) as pool:
        results = list(pool.map(_run_client_round_with_session, active_ids))
    return {"results": [result for result in results if result]}


def _run_client_round_with_session(client_id: str):
    from app.db.session import SessionLocal
    session = SessionLocal()
    try:
        return _run_single_client_round(client_id, session)
    finally:
        session.close()

# Background continuous runner
import threading
import time

_bg_running = False
_bg_thread = None

def _continuous_fl_worker():
    global _bg_running
    from app.db.session import SessionLocal
    while _bg_running:
        try:
            active_ids = [cid for cid, client in simulator.clients.items()
                          if client.status == "ACTIVE"]
            if active_ids:
                with ThreadPoolExecutor(max_workers=len(active_ids)) as pool:
                    list(pool.map(_run_client_round_with_session, active_ids))
        except Exception:
            # Keep the background service alive after a failed client round;
            # transaction details remain available through the API/catalog.
            pass
        time.sleep(0.25)

@router.post("/simulation/start")
def start_continuous_simulation():
    """Starts the continuous background asynchronous federated learning loop."""
    global _bg_running, _bg_thread
    if not _bg_running:
        _bg_running = True
        _bg_thread = threading.Thread(target=_continuous_fl_worker, daemon=True)
        _bg_thread.start()
    return {"simulation_running": True}

@router.post("/simulation/pause")
def pause_continuous_simulation():
    """Pauses the continuous background federated learning loop."""
    global _bg_running
    _bg_running = False
    return {"simulation_running": False}

@router.get("/simulation/status")
def get_simulation_status():
    global _bg_running
    return {"simulation_running": _bg_running}
