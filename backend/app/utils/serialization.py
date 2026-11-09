"""
Serialization and compression utilities for model weights and differential updates.
"""
import io
import base64
from typing import Dict, Any, Tuple
import numpy as np

def serialize_weights_to_base64(weights: np.ndarray) -> str:
    """Serializes a 1D numpy array to a compact base64 string using np.savez_compressed."""
    buf = io.BytesIO()
    np.save(buf, weights.astype(np.float32), allow_pickle=False)
    return base64.b64encode(buf.getvalue()).decode("ascii")

def deserialize_weights_from_base64(encoded: str) -> np.ndarray:
    """Deserializes a base64 string back into a 1D numpy float32 array."""
    data = base64.b64decode(encoded.encode("ascii"))
    buf = io.BytesIO(data)
    return np.load(buf, allow_pickle=False)

def serialize_sparse_delta(delta: np.ndarray, tolerance: float = 1e-4) -> Dict[str, Any]:
    """
    Compresses a dense delta array into a sparse representation:
    non-zero indices, non-zero values, and total length.
    """
    abs_delta = np.abs(delta)
    mask = abs_delta >= tolerance
    indices = np.nonzero(mask)[0].astype(np.int32)
    values = delta[mask].astype(np.float32)
    
    return {
        "length": int(delta.shape[0]),
        "nnz": int(indices.shape[0]),
        "indices_b64": base64.b64encode(indices.tobytes()).decode("ascii"),
        "values_b64": base64.b64encode(values.tobytes()).decode("ascii"),
        "compression_ratio": float(1.0 - (indices.nbytes + values.nbytes) / max(1, delta.nbytes))
    }

def deserialize_sparse_delta(sparse_dict: Dict[str, Any]) -> np.ndarray:
    """Reconstructs a dense 1D delta array from its sparse representation."""
    length = sparse_dict["length"]
    dense = np.zeros(length, dtype=np.float32)
    
    if sparse_dict.get("nnz", 0) > 0:
        raw_idx = base64.b64decode(sparse_dict["indices_b64"])
        raw_val = base64.b64decode(sparse_dict["values_b64"])
        indices = np.frombuffer(raw_idx, dtype=np.int32)
        values = np.frombuffer(raw_val, dtype=np.float32)
        dense[indices] = values
        
    return dense
