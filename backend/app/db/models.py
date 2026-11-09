"""
SQLAlchemy ORM models for the 10 System Catalog Relational Tables.
Matches the official DBMS specification:
1. CLIENTS
2. DATASETS
3. MODEL_VERSIONS
4. TRANSACTIONS
5. VALIDATIONS
6. SCHEDULE_ENTRIES
7. WAL_RECORDS
8. CONFLICT_PREDICTIONS
9. ROLLBACK_EVENTS
10. MODEL_CONTRIBUTIONS
"""
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, ForeignKey, Index, Text
)
from sqlalchemy.orm import relationship
from app.db.session import Base

class Client(Base):
    __tablename__ = "clients"

    client_id = Column(String(50), primary_key=True, index=True)
    client_name = Column(String(100), nullable=False)
    client_type = Column(String(50), nullable=False)  # e.g., 'Commercial', 'Retail', 'FinTech'
    status = Column(String(20), default="ACTIVE", nullable=False)  # ACTIVE, PAUSED, OFFLINE
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    datasets = relationship("Dataset", back_populates="client", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="client")
    contributions = relationship("ModelContribution", back_populates="client")


class Dataset(Base):
    __tablename__ = "datasets"

    dataset_id = Column(String(50), primary_key=True, index=True)
    client_id = Column(String(50), ForeignKey("clients.client_id", ondelete="CASCADE"), nullable=False, index=True)
    dataset_name = Column(String(100), nullable=False)
    record_count = Column(Integer, default=0, nullable=False)
    fraud_ratio = Column(Float, default=0.0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    client = relationship("Client", back_populates="datasets")


class ModelVersion(Base):
    __tablename__ = "model_versions"

    version_id = Column(String(50), primary_key=True, index=True)
    parent_version_id = Column(String(50), ForeignKey("model_versions.version_id"), nullable=True, index=True)
    version_number = Column(Integer, unique=True, nullable=False, index=True)
    checkpoint_path = Column(String(255), nullable=False)
    active_readers = Column(Integer, default=0, nullable=False)
    loss = Column(Float, default=0.0, nullable=False)
    accuracy = Column(Float, default=0.0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    children = relationship("ModelVersion", backref="parent", remote_side=[version_id])
    contributions = relationship("ModelContribution", back_populates="model_version")


class Transaction(Base):
    __tablename__ = "transactions"

    transaction_id = Column(String(50), primary_key=True, index=True)
    client_id = Column(String(50), ForeignKey("clients.client_id"), nullable=False, index=True)
    base_version_id = Column(String(50), ForeignKey("model_versions.version_id"), nullable=False, index=True)
    committed_version_id = Column(String(50), ForeignKey("model_versions.version_id"), nullable=True)
    submitted_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    status = Column(String(20), default="PENDING", nullable=False, index=True)  # PENDING, VALIDATING, COMMITTED, ABORTED, RETRYING
    staleness = Column(Integer, default=0, nullable=False)
    priority_score = Column(Float, default=0.0, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    client = relationship("Client", back_populates="transactions")
    base_version = relationship("ModelVersion", foreign_keys=[base_version_id])
    committed_version = relationship("ModelVersion", foreign_keys=[committed_version_id])

    validations = relationship("Validation", back_populates="transaction", cascade="all, delete-orphan")
    schedule_entry = relationship("ScheduleEntry", uselist=False, back_populates="transaction", cascade="all, delete-orphan")
    wal_records = relationship("WALRecord", back_populates="transaction")
    conflict_prediction = relationship("ConflictPrediction", uselist=False, back_populates="transaction", cascade="all, delete-orphan")
    rollback_event = relationship("RollbackEvent", uselist=False, back_populates="transaction")
    contribution = relationship("ModelContribution", uselist=False, back_populates="transaction")


class Validation(Base):
    __tablename__ = "validations"

    validation_id = Column(String(50), primary_key=True, index=True)
    transaction_id = Column(String(50), ForeignKey("transactions.transaction_id", ondelete="CASCADE"), nullable=False, index=True)
    validation_result = Column(String(30), nullable=False)  # PASSED, REJECTED_STALE, REJECTED_CONFLICT, RETRY_QUEUED
    conflict_score = Column(Float, default=0.0, nullable=False)
    failure_reason = Column(Text, nullable=True)
    checked_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    transaction = relationship("Transaction", back_populates="validations")


class ScheduleEntry(Base):
    __tablename__ = "schedule_entries"

    schedule_id = Column(String(50), primary_key=True, index=True)
    transaction_id = Column(String(50), ForeignKey("transactions.transaction_id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    priority = Column(Float, default=0.0, nullable=False, index=True)
    waiting_time = Column(Float, default=0.0, nullable=False)
    queue_status = Column(String(20), default="QUEUED", nullable=False)  # QUEUED, PROCESSING, DEQUEUED
    enqueued_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    transaction = relationship("Transaction", back_populates="schedule_entry")


class WALRecord(Base):
    __tablename__ = "wal_records"

    log_id = Column(String(50), primary_key=True, index=True)
    lsn = Column(Integer, nullable=False, index=True)
    transaction_id = Column(String(50), ForeignKey("transactions.transaction_id"), nullable=True, index=True)
    record_type = Column(String(20), nullable=False, index=True)  # BEGIN, UPDATE, COMMIT, ABORT, CHECKPOINT, COMPENSATION
    data_reference = Column(String(255), nullable=False)
    checksum = Column(String(64), nullable=False)
    logged_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    transaction = relationship("Transaction", back_populates="wal_records")


class ConflictPrediction(Base):
    __tablename__ = "conflict_predictions"

    prediction_id = Column(String(50), primary_key=True, index=True)
    transaction_id = Column(String(50), ForeignKey("transactions.transaction_id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    risk_score = Column(Float, default=0.0, nullable=False)
    predicted_conflict = Column(Boolean, default=False, nullable=False)
    evaluated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    transaction = relationship("Transaction", back_populates="conflict_prediction")


class RollbackEvent(Base):
    __tablename__ = "rollback_events"

    rollback_id = Column(String(50), primary_key=True, index=True)
    target_transaction_id = Column(String(50), ForeignKey("transactions.transaction_id"), nullable=False, index=True)
    restored_version_id = Column(String(50), ForeignKey("model_versions.version_id"), nullable=False)
    reason = Column(Text, nullable=False)
    rollback_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    status = Column(String(20), default="SUCCESS", nullable=False)

    transaction = relationship("Transaction", back_populates="rollback_event")
    restored_version = relationship("ModelVersion", foreign_keys=[restored_version_id])


class ModelContribution(Base):
    __tablename__ = "model_contributions"

    contribution_id = Column(String(50), primary_key=True, index=True)
    transaction_id = Column(String(50), ForeignKey("transactions.transaction_id"), nullable=False, unique=True, index=True)
    client_id = Column(String(50), ForeignKey("clients.client_id"), nullable=False, index=True)
    model_version_id = Column(String(50), ForeignKey("model_versions.version_id"), nullable=False, index=True)
    update_reference = Column(String(255), nullable=False)
    weight_norm = Column(Float, default=0.0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)  # Set to False if selectively rolled back
    applied_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    transaction = relationship("Transaction", back_populates="contribution")
    client = relationship("Client", back_populates="contributions")
    model_version = relationship("ModelVersion", back_populates="contributions")
