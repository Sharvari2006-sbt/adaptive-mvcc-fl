# Adaptive MVCC-Based Transaction Management and Recovery Framework for Asynchronous Federated Learning

[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-teal.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18.3-61DAFB.svg)](https://react.dev/)
[![TailwindCSS](https://img.shields.io/badge/TailwindCSS-3.4-38B2AC.svg)](https://tailwindcss.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **College DBMS Capstone / Thesis Implementation**  
> A functional, full-stack database transaction coordinator and recovery engine designed specifically for Asynchronous Federated Learning (AFL). Built from first principles in Python with an interactive enterprise monitoring dashboard in React.

---

## 1. Executive Summary & Problem Formulation

In traditional synchronous Federated Learning, a central aggregator waits for all clients to finish training before computing a single model update. In realistic banking deployments, clients operate across disparate hardware, network latencies, and transaction volumes, necessitating **Asynchronous Federated Learning (AFL)**. 

However, asynchronous updates introduce severe classical database anomalies:
1. **Write-Write Conflicts & Parameter Overwrites**: Multiple concurrent client commits overwrite each other's parameters, causing lost updates.
2. **Stale Gradient Decay**: Slow clients compute gradients on older snapshots ($V_{\text{base}}$), which degrade global convergence if applied blindly to advanced versions ($V_{\text{head}}$).
3. **Aggregator Crash Inconsistency**: Mid-aggregation server failure leaves the global model corrupted or unrecoverable without atomicity.
4. **Byzantine & Poisoning Ingestion**: Malicious clients submitting poisoned gradients cannot simply be "deleted" from immutable append-only logs without breaking relational lineage.
5. **Storage Explosion**: Storing complete float32 weight vectors for every intermediate version causes $O(V \cdot |W|)$ disk exhaustion.

### Our Solution
This project implements a **custom, standalone DBMS transaction coordinator** that guarantees ACID properties, snapshot isolation, starvation-free priority scheduling, append-only Write-Ahead Logging with CRC32 checksums, ARIES-style crash recovery, deterministic selective rollback, adaptive garbage collection, and differential delta compression.

---

## 2. System Architecture

```
                    +-----------------------------------------------------------+
                    |          5 Simulated Banking Clients (Private Data)        |
                    |   Bank A (Retail)   Bank B (E-Comm)   Bank C (Intl Cards) |
                    |   Bank D (Credit Union)               Bank E (High-Latency)|
                    +-----------------------------+-----------------------------+
                                                  |
                                (Local Training: ΔW = W_local - W_base)
                                                  v
                    +-----------------------------------------------------------+
                    |               FastAPI Coordinator REST API Layer          |
                    |         (/api/v1/fl, /transactions, /mvcc, /wal, etc.)     |
                    +-----------------------------+-----------------------------+
                                                  |
                                                  v
+----------------------------------------------------------------------------------------------------+
|                                    CUSTOM PYTHON DBMS ENGINE                                        |
|                                                                                                    |
|  [Module 4: Priority Scheduler]  -->  [Module 9: Conflict Predictor]  --> [Module 2: OCC Engine]    |
|  (Starvation-free Aging Queue)         (Feature Risk Scoring)              (Read / Validate / Write)|
|                                                                                       |            |
|                                                                    [Module 3: Adaptive Staleness]  |
|                                                                    (Cosine Utility + τ Threshold)  |
|                                                                                       |            |
|  [Module 10: Differential Storage] <-- [Module 1: MVCC Version Mgr] <-----------------+            |
|  (Sparse Delta Compression)           (DAG Lineage & Snapshot Pins)                                |
|                                                                                                    |
|  [Module 5: Custom WAL Engine]       [Module 6: Crash Recovery]          [Module 7: Selective RB]  |
|  (Append-Only, CRC32, fsync)          (ARIES Analysis, Redo, Undo)        (Deterministic Replay)    |
|                                                                                                    |
|  [Module 8: Adaptive MVCC Garbage Collector]                                                       |
|  (Snapshot-Aware Active Horizon Vacuuming)                                                         |
+-------------------------------------------------+--------------------------------------------------+
                                                  |
                      +---------------------------+---------------------------+
                      |                                                       |
                      v                                                       v
        +----------------------------+                          +----------------------------+
        |   PostgreSQL / SQLite      |                          |   Persistent Disk Storage  |
        |   System Relational Store  |                          |   - active.wal (with CRC)  |
        |   (10 ACID Catalog Tables) |                          |   - checkpoints (*.npy)    |
        |                            |                          |   - deltas (*.npy)         |
        +----------------------------+                          +----------------------------+
```

---

## 3. The 10 Core DBMS Modules

### Module 1: Custom MVCC Version Manager (`app/engine/mvcc.py`)
- Mints immutable monotonic model versions ($V_0, V_1, \dots, V_k$).
- Maintains parent-child lineage in memory and disk DAG.
- **Snapshot Isolation**: When a bank client initiates training, it requests `get_snapshot(client_id)` which registers an active reader pin.
- Protects pinned snapshots from being deleted by garbage collection while training is ongoing.

### Module 2: Optimistic Concurrency Control (OCC) (`app/engine/occ.py`)
- Employs a multi-phase validation lifecycle:
  1. **Read Phase**: Client retrieves snapshot version $V_{\text{base}}$ and executes local training.
  2. **Validation Phase**: Coordinator verifies whether concurrent transactions committed since $V_{\text{base}}$ have clashing or divergent parameters.
  3. **Write / Commit Phase**: Atomic lock serializes the critical commit section, ensuring simultaneous transactions cannot silently overwrite parameters.

### Module 3: Adaptive Staleness Manager (`app/engine/staleness.py`)
- Calculates staleness: $S = V_{\text{current}} - V_{\text{base}}$.
- Dynamic acceptance criterion:
  $$\text{Accept}(T) \iff S \le \tau_{\text{base}} \quad \text{OR} \quad \left(S \le \tau_{\max} \ \land \ \cos(\Delta W, \nabla_{\text{recent}}) > \theta_{\text{threshold}}\right)$$
- If $S \le \tau_{\text{base}}$, the update is accepted with decayed step size $\eta = \frac{1}{\sqrt{1 + S}}$.
- In the margin ($\tau_{\text{base}} < S \le \tau_{\max}$), evaluates cosine similarity with intervening commits; if aligned, it accepts with attenuation; otherwise, rejects.
- Updates with $S > \tau_{\max}$ are rejected unconditionally.
- Thresholds are dynamically configurable from the frontend.

### Module 4: Priority Transaction Scheduler (`app/engine/scheduler.py`)
- Dynamic priority scoring equation:
  $$P = w_{\text{wait}} \cdot t_{\text{wait}} - w_{\text{stale}} \cdot S + w_{\text{fail}} \cdot \text{failures} + \alpha_{\text{aging}} \cdot t_{\text{wait}}^{1.1}$$
- **Starvation Prevention**: Slower institutions (such as Bank E) accumulate priority over time due to the super-linear aging term, ensuring they cannot be starved by high-volume fast banks (Bank A).

### Module 5: Custom Persistent Write-Ahead Logging (`app/engine/wal.py`)
- Physical append-only log file on disk (`active.wal`).
- Format: `[LSN | Log_ID | Txn_ID | Client_ID | Base_Version | Record_Type | Checksum | Timestamp]`.
- Record types: `BEGIN`, `UPDATE`, `COMMIT`, `ABORT`, `CHECKPOINT`, `COMPENSATION`.
- **WAL Invariant 1**: The `UPDATE` log record is forced to physical storage using `os.fsync()` before the in-memory global model is modified.
- **WAL Invariant 2**: The `COMMIT` record is durable before success is reported to the client.
- Computes CRC32 checksum over canonical payload to detect torn writes and file tampering.

### Module 6: ARIES-Style Crash Recovery Manager (`app/engine/recovery.py`)
- **Simulate Crash**: Abruptly drops coordinator memory state, discarding in-flight uncommitted transactions.
- **Restart & Recover Algorithm**:
  1. **Analysis Phase**: Scans backwards to locate the latest valid `CHECKPOINT` snapshot and scans forward to identify transactions.
  2. **Redo Phase**: Replays all `UPDATE` records for transactions that have a matching `COMMIT` in strict LSN order.
  3. **Undo Phase**: Marks all in-flight or uncommitted transactions as `ABORTED` in the database catalog.
  4. Restores last consistent global model version and rehydrates MVCC cache.

### Module 7: Selective Rollback Manager (`app/engine/rollback.py`)
- When adversarial or poisoned gradients are detected (e.g. Bank C injection):
- Does **NOT** mutate or delete immutable WAL records (which would violate database audit immutability).
- Instead, logs a `COMPENSATION` record and deterministically replays all subsequent valid contributions from the nearest checkpoint baseline, omitting only the poisoned transaction.
- Mints a clean corrected model version $V_{\text{clean}}$ with full audit trace.

### Module 8: Adaptive MVCC Garbage Collector (`app/engine/gc.py`)
- Background vacuum engine.
- Calculates safe horizon: $V_{\text{safe}} = \min(\{\text{Pinned Snapshots}\} \cup \{V_{\text{head}}\})$.
- Preserves pinned snapshots, head version, and checkpoints.
- Safely reclaims storage for unreferenced intermediate versions and reports freed bytes before and after execution.

### Module 9: Transaction Conflict Prediction (`app/engine/predictor.py`)
- Advisory pre-validation risk evaluator.
- Evaluates features: client past abort rates, staleness factor, scheduler contention, and gradient L2 norm.
- Computes calibrated risk score $R \in [0.0, 1.0]$ and categorizes transaction into LOW, MEDIUM, or HIGH risk.
- **Strict Invariant**: Predictions are advisory and never bypass mandatory OCC validation.

### Module 10: Differential WAL Storage Manager (`app/engine/differential.py`)
- Calculates sparse parameter deltas: $\Delta W = W_{\text{new}} - W_{\text{base}}$.
- Stores only non-zero coordinates and values rather than repeated full $D$-dimensional float arrays.
- Reconstructs target versions on-demand by delta accumulation.
- Reports current sparse-delta payload estimates against full float32 model sizes; savings depend on update sparsity and are not hardcoded.

---

## 4. PostgreSQL Relational Database Schema

The catalog consists of 10 fully normalized tables with primary keys, foreign keys, indexes, and constraints:

1. **`clients`**: `client_id` (PK), `client_name`, `client_type`, `status`, `created_at`.
2. **`datasets`**: `dataset_id` (PK), `client_id` (FK), `dataset_name`, `record_count`, `fraud_ratio`, `created_at`.
3. **`model_versions`**: `version_id` (PK), `parent_version_id` (FK), `version_number`, `checkpoint_path`, `active_readers`, `loss`, `accuracy`, `created_at`.
4. **`transactions`**: `transaction_id` (PK), `client_id` (FK), `base_version_id` (FK), `committed_version_id` (FK), `status`, `staleness`, `priority_score`, `submitted_at`, `completed_at`.
5. **`validations`**: `validation_id` (PK), `transaction_id` (FK), `validation_result`, `conflict_score`, `failure_reason`, `checked_at`.
6. **`schedule_entries`**: `schedule_id` (PK), `transaction_id` (FK), `priority`, `waiting_time`, `queue_status`, `enqueued_at`.
7. **`wal_records`**: `log_id` (PK), `lsn`, `transaction_id` (FK), `record_type`, `data_reference`, `checksum`, `logged_at`.
8. **`conflict_predictions`**: `prediction_id` (PK), `transaction_id` (FK), `risk_score`, `predicted_conflict`, `evaluated_at`.
9. **`rollback_events`**: `rollback_id` (PK), `target_transaction_id` (FK), `restored_version_id` (FK), `reason`, `rollback_at`, `status`.
10. **`model_contributions`**: `contribution_id` (PK), `transaction_id` (FK), `client_id` (FK), `model_version_id` (FK), `update_reference`, `weight_norm`, `is_active`, `applied_at`.

---

## 5. Simulated Banking Clients

| Client | Profile | Record Count | Fraud Rate | Latency | Default Characteristics |
|---|---|---|---|---|---|
| **Bank A** | National Retail | 5,000 | 1.5% | 0.2s | High transaction volume, fast submissions |
| **Bank B** | Global E-Commerce | 4,000 | 3.8% | 0.4s | High online bias, moderate volume |
| **Bank C** | Cross-Border Cards | 3,500 | 5.5% | 0.6s | High volatility, configurable for malicious poisoning |
| **Bank D** | Regional Credit Union | 2,000 | 0.9% | 0.8s | Low volume, configurable for stale submissions |
| **Bank E** | Rural Community | 1,500 | 1.8% | 2.0s | High network delay, tests starvation-free priority aging |

> **Privacy Guarantee**: Bank clients never transmit raw customer transaction records. Only model weight differences ($\Delta W$) are transmitted to the coordinator.

---

## 6. Frontend Dashboard (7 Pages)

Built with **React.js, Vite, Tailwind CSS, Recharts, and Lucide icons**:
1. **Overview Dashboard**: High-level KPIs, model accuracy convergence curve, client throughput breakdown, and anomaly preset triggers.
2. **Client Management**: Interactive bank cards for Bank A–E with status toggles, latency sliders, outdated snapshot force, and malicious poisoning toggle.
3. **Transaction Explorer**: Filterable OCC ledger (COMMITTED, ABORTED, PENDING, VALIDATING), priority queue viewer, and deep transaction inspection drawer.
4. **MVCC Version Explorer**: Directed acyclic graph lineage tree, active snapshot reader pins, and parameter tensor statistics.
5. **WAL & Crash Recovery**: Live append-only log stream, CRC32 integrity monitor, "Simulate Server Crash" and "Restart and Recover" controls.
6. **Optimization Center**: Dedicated interactive evaluation tabs for all 6 novelty modules with real-time controls.
7. **Reports & Analytics**: Accuracy vs Loss curves, storage comparison, a deterministic last-writer-wins replay comparison, and one-click "Download Experiment Results CSV" export.

---

## 7. Setup & Execution Instructions

### Prerequisites
- Python 3.11+ (Python 3.12 recommended)
- Node.js 18+ and npm
- (Optional) Docker Compose for PostgreSQL

### Option A: One-Click Windows Launch
Double-click or run:
```bat
run_all.bat
```
This automatically starts:
- Backend API server on `http://127.0.0.1:8000` (Swagger docs: `/docs`)
- Frontend React Dashboard on `http://localhost:5173`
- Opens your default web browser to the dashboard.

### Option B: Manual Setup

1. **Backend**:
```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

2. **Frontend**:
```bash
cd frontend
npm install
npm run dev
```

3. **Using PostgreSQL with Docker Compose**:
```bash
docker compose up -d db
set DATABASE_URL=postgresql://postgres:postgrespassword@localhost:5432/mvcc_fl
cd backend
alembic -c alembic.ini upgrade head
```

The application uses SQLite by default for a zero-configuration local demo.
PostgreSQL is the intended shared catalog for deployment. Alembic migrations
are under `backend/migrations`; run the migration command after configuring
`DATABASE_URL` and before starting the API. Startup also runs `create_all` so
fresh demo installs remain easy to launch.

---

## 8. Verification & Automated Test Suite

The test suite includes **33 automated tests** covering all 12 specification scenarios, including recovery of a durable commit whose model version had not yet reached the catalog, concurrent same-snapshot updates without lost contributions, checkpoint WAL lock handling, and concurrent rounds across all five simulated banks:

```bash
cd backend
set PYTHONPATH=.
..\venv\Scripts\pytest.exe tests/ -v
```

### Coverage of All 12 Required Specification Scenarios:
1. `test_scenario_1_multiple_clients_submitting_simultaneously`: Verified concurrent thread submissions without lost updates.
2. `test_scenario_2_two_transactions_using_same_snapshot`: Verified concurrent branches off snapshot $V_0$.
3. `test_scenario_3_stale_update_rejection`: Verified rejection of updates exceeding maximum staleness bound.
4. `test_scenario_4_priority_scheduling_and_starvation_prevention`: Verified that aging boosts slow client priority over newer transactions.
5. `test_scenario_5_wal_persistence_before_commit`: Verified physical file contains `UPDATE` and `COMMIT` with CRC32 before in-memory publish.
6. `test_scenario_6_crash_during_incomplete_transaction`: Verified that uncommitted transactions at crash time are rolled back (marked `ABORTED`).
7. `test_scenario_7_recovery_of_committed_transactions`: Verified ARIES redo of committed updates in strict LSN sequence.
8. `test_scenario_8_selective_rollback_of_a_malicious_contribution`: Verified deterministic model reconstruction omitting poisoned update while preserving valid commits.
9. `test_scenario_9_garbage_collection_with_active_snapshots`: Verified that pinned snapshots are protected during vacuum.
10. `test_scenario_10_differential_log_reconstruction`: Verified ground-truth weight reconstruction from base checkpoint and delta chain.
11. `test_scenario_11_corrupted_wal_record_detection`: Verified that CRC32 checksum validation pinpoints tampered WAL lines.
12. `test_scenario_12_conflict_prediction_vs_actual_conflicts`: Verified risk scoring calibration without bypassing mandatory OCC validation.

---

## 9. Live Professor Demonstration Script

When demonstrating this project to a DBMS evaluation committee:

1. **Demonstrate Snapshot Isolation & OCC (Overview -> Step Round)**:
   - Click "Step FL Round" on the Header.
   - Show how Bank A reads $V_0$, submits $\Delta W$, and commits $V_1$.
   - Inspect the **Transaction Explorer** to show the transaction transition from `PENDING` -> `VALIDATING` -> `COMMITTED`.

2. **Demonstrate Adaptive Staleness**:
   - Go to **Client Management**, click `Stale V0` on Bank D.
   - Click "Step Bank Round".
   - Navigate to **Transaction Explorer**: observe that Bank D submitted against $V_0$ while the head is $V_4+$.
   - Point out that it was rejected with status `ABORTED` (`REJECTED_STALE`) because staleness exceeded allowance.

3. **Demonstrate Starvation Prevention**:
   - Go to **Optimization Center -> 2. Priority Scheduling**.
   - Show the dynamic aging formula. Observe how Bank E (high latency) gains priority the longer it waits in queue.

4. **Demonstrate Persistent WAL & Crash Recovery**:
   - Go to **WAL & Crash Recovery**.
   - Review the append-only stream and show that every record has an 8-character CRC32 checksum.
   - Click **Simulate Server Crash**: show that the server enters crashed status.
   - Click **Restart & Recover**: observe the live ARIES recovery execution report showing checkpoint LSN, committed transactions redone, and discarded incomplete transactions.

5. **Demonstrate Selective Rollback (Poisoning Mitigation)**:
   - Go to **Client Management**, toggle `Poison` on Bank C.
   - Click "Step FL Round" to commit the poisoned transaction.
   - Go to **Optimization Center -> 3. Selective Rollback**.
   - Enter the poisoned transaction ID and click **Execute Deterministic Selective Rollback**.
   - Point out that the WAL file was **not** deleted; rather, a `COMPENSATION` record was appended and valid updates re-aggregated into a clean model version.

6. **Demonstrate Differential WAL Storage Savings**:
   - Go to **Optimization Center -> 6. Differential Storage**.
   - Show the live comparison graph for full-model bytes versus the current sparse-delta estimate. The result varies with observed updates.

7. **Download CSV Audit Log**:
   - Go to **Reports & Analytics** and click **Download Experiment Results (CSV)**. Show the downloaded audit log containing the full transaction and version history.
