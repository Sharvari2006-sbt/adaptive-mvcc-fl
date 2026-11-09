"""
Module 10: Differential WAL Storage Manager
Calculates weight deltas, compresses sparse parameter updates, reconstructs historical models
from delta sequences, and quantifies disk storage savings compared to full-model snapshot logging.
"""
from typing import Dict, Any, List, Tuple
import numpy as np
from app.utils.serialization import serialize_sparse_delta, deserialize_sparse_delta

class DifferentialStorageManager:
    """
    Manages differential weight logging and model state reconstruction.
    """
    def __init__(self):
        # Tracking metrics for analytics comparison
        self.total_full_model_bytes: int = 0
        self.total_differential_bytes: int = 0
        self.total_deltas_logged: int = 0

    def calculate_delta(self, base_weights: np.ndarray, new_weights: np.ndarray) -> np.ndarray:
        """Computes weight difference: delta = new - base."""
        return (new_weights - base_weights).astype(np.float32)

    def record_storage_metrics(self, full_model_weights: np.ndarray, delta: np.ndarray):
        """Quantifies byte consumption of full model vs sparse differential delta."""
        full_size = full_model_weights.nbytes
        sparse_meta = serialize_sparse_delta(delta)
        # Approximate storage of sparse delta (indices + values in bytes)
        indices_bytes = sparse_meta["nnz"] * 4
        values_bytes = sparse_meta["nnz"] * 4
        diff_size = indices_bytes + values_bytes + 64  # including header metadata overhead

        self.total_full_model_bytes += full_size
        self.total_differential_bytes += diff_size
        self.total_deltas_logged += 1

    def reconstruct_model_from_deltas(
        self,
        checkpoint_weights: np.ndarray,
        delta_chain: List[np.ndarray]
    ) -> np.ndarray:
        """
        Reconstructs target model version by sequentially applying a list of deltas
        onto the nearest base checkpoint snapshot.
        """
        reconstructed = checkpoint_weights.copy()
        for delta in delta_chain:
            reconstructed += delta
        return reconstructed.astype(np.float32)

    def get_comparison_metrics(self) -> Dict[str, Any]:
        """Returns comparison analytics between naive full-model logging and differential logging."""
        full_mb = self.total_full_model_bytes / (1024 * 1024)
        diff_mb = self.total_differential_bytes / (1024 * 1024)
        savings_mb = max(0.0, full_mb - diff_mb)
        savings_pct = (savings_mb / full_mb * 100.0) if full_mb > 0 else 0.0

        return {
            "total_versions_logged": self.total_deltas_logged,
            "full_model_logging_bytes": self.total_full_model_bytes,
            "full_model_logging_mb": round(full_mb, 4),
            "differential_logging_bytes": self.total_differential_bytes,
            "differential_logging_mb": round(diff_mb, 4),
            "storage_saved_mb": round(savings_mb, 4),
            "storage_reduction_percent": round(savings_pct, 2)
        }
