"""
Module 3: Adaptive Staleness Manager
Calculates transaction staleness and evaluates utility to dynamically accept, scale, or reject updates.
"""
from typing import Tuple, Dict, Any, Optional
import numpy as np

class AdaptiveStalenessManager:
    """
    Manages staleness-aware validation:
    Staleness = Current Model Version Number - Client Base Version Number
    """
    def __init__(
        self,
        base_threshold: int = 3,
        max_allowance: int = 6,
        cosine_threshold: float = 0.20
    ):
        self.base_threshold = base_threshold
        self.max_allowance = max_allowance
        self.cosine_threshold = cosine_threshold

    def update_config(self, base_threshold: Optional[int] = None, max_allowance: Optional[int] = None, cosine_threshold: Optional[float] = None):
        """Allows dynamic configuration from the dashboard."""
        if base_threshold is not None:
            self.base_threshold = max(0, int(base_threshold))
        if max_allowance is not None:
            self.max_allowance = max(self.base_threshold, int(max_allowance))
        if cosine_threshold is not None:
            self.cosine_threshold = float(cosine_threshold)

    def calculate_staleness(self, current_version_num: int, base_version_num: int) -> int:
        """Returns integer staleness: delta in version numbers."""
        return max(0, current_version_num - base_version_num)

    def evaluate_staleness(
        self,
        staleness: int,
        client_delta: np.ndarray,
        recent_accumulated_delta: Optional[np.ndarray] = None
    ) -> Tuple[bool, str, float, float]:
        """
        Evaluates whether an update is acceptable despite staleness.
        Returns:
            (is_acceptable: bool, decision_reason: str, utility_score: float, scaling_factor: float)
        """
        # Case 1: Fresh update (Staleness = 0)
        if staleness == 0:
            return True, "FRESH_UPDATE", 1.0, 1.0

        # Case 2: Within base threshold
        if staleness <= self.base_threshold:
            # Linear decay of scaling factor to prevent stale gradients from causing overshoot
            decay = 1.0 / np.sqrt(1.0 + staleness)
            utility = float(1.0 - (staleness / (self.max_allowance + 1)))
            return True, f"ACCEPTED_RECENT_STALENESS_{staleness}", utility, float(decay)

        # Case 3: Beyond max allowance -> Absolute rejection
        if staleness > self.max_allowance:
            return False, f"REJECTED_EXCESSIVE_STALENESS_{staleness}_MAX_{self.max_allowance}", 0.0, 0.0

        # Case 4: In adaptive margin (base_threshold < staleness <= max_allowance)
        # Check cosine similarity with intervening commits to determine if gradient direction is still valid
        if recent_accumulated_delta is not None and recent_accumulated_delta.shape == client_delta.shape:
            norm_c = np.linalg.norm(client_delta)
            norm_r = np.linalg.norm(recent_accumulated_delta)
            
            if norm_c > 1e-7 and norm_r > 1e-7:
                cos_sim = float(np.dot(client_delta, recent_accumulated_delta) / (norm_c * norm_r))
            else:
                cos_sim = 0.0

            if cos_sim >= self.cosine_threshold:
                # Aligned with recent trajectory: accept with conservative learning rate
                attenuation = 1.0 / (1.0 + staleness)
                utility = float(cos_sim * (1.0 - staleness / (self.max_allowance + 2)))
                return True, f"ACCEPTED_ADAPTIVE_COSINE_{cos_sim:.2f}", utility, float(attenuation)
            else:
                return False, f"REJECTED_DIVERGENT_STALENESS_COS_{cos_sim:.2f}", 0.1, 0.0

        # Default fallback if no gradient comparison available: reject in margin
        return False, f"REJECTED_MARGINAL_STALENESS_{staleness}", 0.1, 0.0
