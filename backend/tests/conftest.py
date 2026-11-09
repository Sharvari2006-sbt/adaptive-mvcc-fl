"""
Shared pytest configuration and fixtures for DBMS test suites.
Ensures clean foreign-key-safe table cleaning between test executions.
"""
import sys
import os
from pathlib import Path

# Automatically ensure the backend directory is in sys.path regardless of execution environment
backend_path = Path(__file__).resolve().parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

import pytest
from app.db.session import SessionLocal, init_db
from app.db.models import (
    ScheduleEntry, ConflictPrediction, RollbackEvent,
    ModelContribution, WALRecord, Validation, Transaction
)

def clean_operational_tables(db):
    """Deletes rows in strict child-first dependency order to respect foreign key constraints."""
    db.query(ScheduleEntry).delete()
    db.query(ConflictPrediction).delete()
    db.query(RollbackEvent).delete()
    db.query(ModelContribution).delete()
    db.query(WALRecord).delete()
    db.query(Validation).delete()
    db.query(Transaction).delete()
    db.commit()

@pytest.fixture(autouse=True)
def auto_clean_db():
    init_db()
    db = SessionLocal()
    try:
        clean_operational_tables(db)
    except Exception:
        db.rollback()
    finally:
        db.close()
    yield
    db = SessionLocal()
    try:
        clean_operational_tables(db)
    except Exception:
        db.rollback()
    finally:
        db.close()
