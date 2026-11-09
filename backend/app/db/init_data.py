"""
System Initialization Script:
Registers the 5 simulated banks, generates their private datasets, and mints Genesis Model Version V0.
"""
from datetime import datetime
from pathlib import Path
from sqlalchemy.orm import Session
from app.config import CHECKPOINTS_DIR
from app.db.session import SessionLocal, init_db
from app.db.models import Client, Dataset, ModelVersion
from app.fl.dataset import CLIENT_PROFILES, ensure_all_datasets_exist
from app.fl.model import get_initial_weights, FraudDetectionNN, compute_model_metrics, set_flat_params
from app.utils.serialization import serialize_weights_to_base64
import pandas as pd

def seed_system(db: Session):
    """Idempotently seeds clients, datasets, and initial model version V0."""
    init_db()
    
    # 1. Register the 5 banks
    for cid, profile in CLIENT_PROFILES.items():
        existing_client = db.query(Client).filter(Client.client_id == cid).first()
        if not existing_client:
            client = Client(
                client_id=cid,
                client_name=profile["name"],
                client_type=profile["type"],
                status="ACTIVE",
                created_at=datetime.utcnow()
            )
            db.add(client)
    db.commit()
    
    # 2. Generate and catalog datasets
    generated_datasets = ensure_all_datasets_exist()
    for cid, (fpath, count, fraud_ratio) in generated_datasets.items():
        existing_ds = db.query(Dataset).filter(Dataset.dataset_id == f"ds_{cid}").first()
        if not existing_ds:
            ds = Dataset(
                dataset_id=f"ds_{cid}",
                client_id=cid,
                dataset_name=f"{cid.upper()}_Fraud_Transactions",
                record_count=count,
                fraud_ratio=fraud_ratio,
                created_at=datetime.utcnow()
            )
            db.add(ds)
    db.commit()
    
    # 3. Mint Genesis Model Version V0
    v0 = db.query(ModelVersion).filter(ModelVersion.version_number == 0).first()
    if not v0:
        initial_w = get_initial_weights()
        v0_path = CHECKPOINTS_DIR / "v0_checkpoint.npy"
        import numpy as np
        np.save(v0_path, initial_w)
        
        # Calculate baseline metrics on a sample
        sample_df = pd.read_csv(list(generated_datasets.values())[0][0])
        from app.fl.dataset import FEATURE_COLUMNS
        X_sample = sample_df[FEATURE_COLUMNS].values[:500]
        y_sample = sample_df["is_fraud"].values[:500]
        
        model = FraudDetectionNN()
        set_flat_params(model, initial_w)
        loss, acc = compute_model_metrics(model, X_sample, y_sample)
        
        v0 = ModelVersion(
            version_id="v0",
            parent_version_id=None,
            version_number=0,
            checkpoint_path=str(v0_path),
            active_readers=0,
            loss=loss,
            accuracy=acc,
            created_at=datetime.utcnow()
        )
        db.add(v0)
        db.commit()
        print("[System Seed] Initialized Genesis Model Version v0.")
    else:
        print("[System Seed] Genesis Model Version v0 already exists.")

if __name__ == "__main__":
    db = SessionLocal()
    try:
        seed_system(db)
    finally:
        db.close()
