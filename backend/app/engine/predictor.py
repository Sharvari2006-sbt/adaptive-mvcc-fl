"""
Module 9: Transaction Conflict Prediction Engine
Computes an advisory conflict risk score using client historical abort rates,
current staleness, queue contention, and gradient magnitude.
IMPORTANT: Predictions are purely advisory and NEVER bypass mandatory OCC validation.
"""
from typing import Dict, Any, Optional
import numpy as np
from datetime import datetime
from sqlalchemy.orm import Session
from app.db.models import ConflictPrediction, Transaction

class TransactionConflictPredictor:
    """
    Evaluates transaction risk score R in [0.0, 1.0] before OCC validation.
    """
    def __init__(self):
        # Weights for heuristic scoring features
        self.w_staleness = 0.35
        self.w_client_history = 0.25
        self.w_queue_contention = 0.20
        self.w_gradient_norm = 0.20

    def predict_risk(
        self,
        txn_id: str,
        client_id: str,
        staleness: int,
        client_delta: np.ndarray,
        current_queue_depth: int,
        db: Session
    ) -> Dict[str, Any]:
        """
        Calculates conflict risk score R in [0.0, 1.0] and classifies risk category.
        Logs to conflict_predictions table in the relational catalog.
        """
        # Feature 1: Staleness factor (normalized against max allowance of 6)
        staleness_factor = min(1.0, staleness / 5.0)

        # Feature 2: Historical abort rate for this client
        total_txns = db.query(Transaction).filter(Transaction.client_id == client_id).count()
        aborted_txns = db.query(Transaction).filter(
            Transaction.client_id == client_id,
            Transaction.status == "ABORTED"
        ).count()
        abort_ratio = (aborted_txns / total_txns) if total_txns > 0 else 0.1

        # Feature 3: Queue contention factor
        contention_factor = min(1.0, current_queue_depth / 5.0)

        # Feature 4: Delta norm outlier factor (large gradient deltas are more likely to clash)
        norm = float(np.linalg.norm(client_delta))
        norm_factor = min(1.0, norm / 2.0)

        # Weighted aggregate risk score
        risk_score = (
            self.w_staleness * staleness_factor
            + self.w_client_history * abort_ratio
            + self.w_queue_contention * contention_factor
            + self.w_gradient_norm * norm_factor
        )
        risk_score = float(np.clip(risk_score, 0.0, 1.0))
        predicted_conflict = risk_score >= 0.50

        # Persist prediction to relational catalog
        db_pred = ConflictPrediction(
            prediction_id=f"pred_{txn_id}",
            transaction_id=txn_id,
            risk_score=round(risk_score, 4),
            predicted_conflict=predicted_conflict,
            evaluated_at=datetime.utcnow()
        )
        db.add(db_pred)
        db.commit()

        risk_category = "LOW"
        if risk_score >= 0.70:
            risk_category = "HIGH"
        elif risk_score >= 0.40:
            risk_category = "MEDIUM"

        return {
            "prediction_id": db_pred.prediction_id,
            "transaction_id": txn_id,
            "risk_score": round(risk_score, 4),
            "predicted_conflict": predicted_conflict,
            "risk_category": risk_category,
            "feature_breakdown": {
                "staleness_factor": round(staleness_factor, 3),
                "client_abort_ratio": round(abort_ratio, 3),
                "contention_factor": round(contention_factor, 3),
                "norm_factor": round(norm_factor, 3)
            },
            "note": "Advisory prediction score; mandatory OCC validation will strictly execute."
        }
