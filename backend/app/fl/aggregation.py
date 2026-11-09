"""
Deterministic Model Parameter Aggregation for Asynchronous Federated Learning.
Computes new global weights by applying validated weight deltas with optional learning rate attenuation.
"""
from typing import Tuple
import numpy as np

def apply_weight_delta(
    base_weights: np.ndarray,
    delta: np.ndarray,
    scaling_factor: float = 1.0,
    global_lr: float = 1.0
) -> np.ndarray:
    """
    Applies a validated client delta to the base model weights deterministically:
    W_new = W_base + (global_lr * scaling_factor) * delta
    """
    effective_step = global_lr * scaling_factor
    new_weights = base_weights + (effective_step * delta)
    return new_weights.astype(np.float32)

def compute_weight_norm(weights_or_delta: np.ndarray) -> float:
    """Calculates Euclidean L2 norm of weights or delta vector."""
    return float(np.linalg.norm(weights_or_delta))
