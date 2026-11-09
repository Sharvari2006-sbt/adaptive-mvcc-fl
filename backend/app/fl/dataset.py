"""
Synthetic Banking Fraud Detection Dataset Generator for Federated Clients.
Simulates realistic, non-IID data distributions for Bank A, Bank B, Bank C, Bank D, and Bank E.
Never transmits raw records to the central coordinator.
"""
from pathlib import Path
import numpy as np
import pandas as pd
from app.config import DATASETS_DIR

CLIENT_PROFILES = {
    "bank_a": {
        "name": "Bank A - National Retail Bank",
        "type": "Retail Banking",
        "record_count": 5000,
        "fraud_ratio": 0.015,
        "foreign_bias": 0.05,
        "online_bias": 0.40,
        "amount_mean": 80.0,
        "amount_std": 50.0,
    },
    "bank_b": {
        "name": "Bank B - Global E-Commerce Bank",
        "type": "Digital Merchant",
        "record_count": 4000,
        "fraud_ratio": 0.038,
        "foreign_bias": 0.25,
        "online_bias": 0.95,
        "amount_mean": 120.0,
        "amount_std": 110.0,
    },
    "bank_c": {
        "name": "Bank C - Cross-Border Card Issuer",
        "type": "International Cards",
        "record_count": 3500,
        "fraud_ratio": 0.055,
        "foreign_bias": 0.65,
        "online_bias": 0.70,
        "amount_mean": 210.0,
        "amount_std": 180.0,
    },
    "bank_d": {
        "name": "Bank D - Regional Credit Union",
        "type": "Credit Union",
        "record_count": 2000,
        "fraud_ratio": 0.009,
        "foreign_bias": 0.02,
        "online_bias": 0.25,
        "amount_mean": 65.0,
        "amount_std": 40.0,
    },
    "bank_e": {
        "name": "Bank E - Rural Community Bank",
        "type": "Community Banking",
        "record_count": 1500,
        "fraud_ratio": 0.018,
        "foreign_bias": 0.01,
        "online_bias": 0.20,
        "amount_mean": 55.0,
        "amount_std": 35.0,
    },
}

FEATURE_COLUMNS = [
    "amount_norm",
    "hour_of_day_norm",
    "is_foreign",
    "is_online",
    "card_present",
    "velocity_1h_norm",
    "merchant_risk_score",
    "distance_km_norm",
    "device_trust_score",
    "credit_utilization"
]

def generate_bank_dataset(client_id: str, seed: int = 42) -> pd.DataFrame:
    """Generates synthetic fraud transaction dataset for a specific bank client."""
    profile = CLIENT_PROFILES.get(client_id)
    if not profile:
        raise ValueError(f"Unknown client_id: {client_id}")
    
    rng = np.random.RandomState(seed + hash(client_id) % 10000)
    n = profile["record_count"]
    fraud_rate = profile["fraud_ratio"]
    
    # 1. Amounts
    amounts = rng.lognormal(mean=np.log(max(10.0, profile["amount_mean"])), sigma=0.6, size=n)
    
    # 2. Hour of day (0-23)
    hours = rng.randint(0, 24, size=n)
    
    # 3. Categorical flags based on profile biases
    is_foreign = (rng.rand(n) < profile["foreign_bias"]).astype(float)
    is_online = (rng.rand(n) < profile["online_bias"]).astype(float)
    card_present = (1.0 - is_online) * (rng.rand(n) > 0.1).astype(float)
    
    # 4. Behavioral signals
    velocity_1h = rng.poisson(lam=1.5, size=n).astype(float)
    merchant_risk = rng.beta(a=2, b=5, size=n)
    distance_km = rng.exponential(scale=15.0, size=n)
    device_trust = rng.beta(a=5, b=2, size=n)
    credit_util = rng.uniform(0.05, 0.95, size=n)
    
    # Latent fraud score calculation
    fraud_score = (
        0.35 * (amounts / 200.0)
        + 0.25 * is_foreign
        + 0.20 * is_online
        + 0.30 * (velocity_1h / 4.0)
        + 0.40 * merchant_risk
        + 0.25 * (distance_km / 50.0)
        - 0.35 * device_trust
        + 0.20 * credit_util
        + rng.normal(0, 0.15, size=n)
    )
    
    # Top percentile assigned as fraud
    cutoff = np.percentile(fraud_score, 100.0 * (1.0 - fraud_rate))
    is_fraud = (fraud_score >= cutoff).astype(int)
    
    # Normalize features for neural network ingestion
    df = pd.DataFrame({
        "amount_norm": (amounts - amounts.mean()) / (amounts.std() + 1e-6),
        "hour_of_day_norm": (hours - 12.0) / 12.0,
        "is_foreign": is_foreign,
        "is_online": is_online,
        "card_present": card_present,
        "velocity_1h_norm": (velocity_1h - 1.5) / 2.0,
        "merchant_risk_score": merchant_risk,
        "distance_km_norm": np.clip(distance_km / 100.0, 0.0, 2.0),
        "device_trust_score": device_trust,
        "credit_utilization": credit_util,
        "is_fraud": is_fraud
    })
    
    return df

def ensure_all_datasets_exist():
    """Generates and saves datasets for Bank A-E locally."""
    DATASETS_DIR.mkdir(parents=True, exist_ok=True)
    generated = {}
    for cid in CLIENT_PROFILES.keys():
        file_path = DATASETS_DIR / f"{cid}_fraud.csv"
        if not file_path.exists():
            df = generate_bank_dataset(cid)
            df.to_csv(file_path, index=False)
            generated[cid] = (file_path, len(df), float(df["is_fraud"].mean()))
        else:
            df = pd.read_csv(file_path)
            generated[cid] = (file_path, len(df), float(df["is_fraud"].mean()))
    return generated
