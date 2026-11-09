"""
Simulated Federated Learning Clients (Bank A, Bank B, Bank C, Bank D, Bank E).
Each client holds a distinct private local dataset and executes local gradient updates.
Supports delays, outdated snapshots, and malicious weight poisoning injection.
Never transmits raw customer records.
"""
from typing import Dict, Any, Optional, Tuple, Callable, List
import time
import threading
from pathlib import Path
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from app.config import DATASETS_DIR, settings
from app.fl.dataset import CLIENT_PROFILES, FEATURE_COLUMNS
from app.fl.model import FraudDetectionNN, get_flat_params, set_flat_params, compute_model_metrics

class BankClient:
    """Represents an independent banking institution in the AFL federation."""
    def __init__(
        self,
        client_id: str,
        name: str,
        client_type: str,
        delay_seconds: float = 0.5
    ):
        self.client_id = client_id
        self.name = name
        self.client_type = client_type
        self.delay_seconds = delay_seconds
        self.status = "ACTIVE"  # ACTIVE, PAUSED, OFFLINE
        self.is_malicious = False
        self.force_outdated = False
        self.current_snapshot_vid: Optional[str] = None
        self.last_loss = 0.0
        self.last_accuracy = 0.0
        self.last_submitted_at: Optional[str] = None
        self.total_submissions = 0
        self.successful_commits = 0
        self.aborted_txns = 0

        # Load local private dataset
        self.data_file = DATASETS_DIR / f"{client_id}_fraud.csv"
        self._X: Optional[np.ndarray] = None
        self._y: Optional[np.ndarray] = None
        self._load_local_dataset()

    def _load_local_dataset(self):
        if self.data_file.exists():
            df = pd.read_csv(self.data_file)
            self._X = df[FEATURE_COLUMNS].values.astype(np.float32)
            self._y = df["is_fraud"].values.astype(np.float32)

    def train_local_step(
        self,
        base_weights: np.ndarray,
        epochs: int = 1,
        lr: float = settings.LEARNING_RATE
    ) -> Tuple[np.ndarray, float, float]:
        """
        Executes local PyTorch training over private client dataset.
        Computes delta = W_trained - W_base.
        Does NOT transmit raw records.
        """
        if self._X is None or len(self._X) == 0:
            self._load_local_dataset()

        # Simulate configurable client network / computational latency
        if self.delay_seconds > 0:
            time.sleep(min(self.delay_seconds, 2.0))

        # Check for malicious poisoning injection
        if self.is_malicious:
            # Poisoning attack: inject adversarial weight surge
            poisoned_delta = (np.random.randn(*base_weights.shape).astype(np.float32) * 2.5) - (base_weights * 1.5)
            return poisoned_delta, 1.85, 0.25

        # Standard local training
        model = FraudDetectionNN()
        set_flat_params(model, base_weights)
        model.train()

        criterion = nn.BCEWithLogitsLoss()
        optimizer = torch.optim.SGD(model.parameters(), lr=lr, momentum=0.8)

        dataset = torch.utils.data.TensorDataset(
            torch.tensor(self._X, dtype=torch.float32),
            torch.tensor(self._y, dtype=torch.float32).unsqueeze(1)
        )
        loader = torch.utils.data.DataLoader(dataset, batch_size=64, shuffle=True)

        for _ in range(epochs):
            for batch_x, batch_y in loader:
                optimizer.zero_grad()
                pred = model(batch_x)
                loss = criterion(pred, batch_y)
                loss.backward()
                optimizer.step()

        trained_weights = get_flat_params(model)
        delta = trained_weights - base_weights

        loss_eval, acc_eval = compute_model_metrics(model, self._X[:400], self._y[:400])
        self.last_loss = loss_eval
        self.last_accuracy = acc_eval
        return delta, loss_eval, acc_eval


class ClientSimulationManager:
    """Manages the 5 simulated bank clients and orchestrates asynchronous AFL client rounds."""
    def __init__(self):
        self.clients: Dict[str, BankClient] = {
            "bank_a": BankClient("bank_a", "Bank A - National Retail", "Retail Banking", delay_seconds=0.2),
            "bank_b": BankClient("bank_b", "Bank B - Global E-Commerce", "Digital Merchant", delay_seconds=0.4),
            "bank_c": BankClient("bank_c", "Bank C - Cross-Border Cards", "International Cards", delay_seconds=0.6),
            "bank_d": BankClient("bank_d", "Bank D - Regional Credit Union", "Credit Union", delay_seconds=0.8),
            "bank_e": BankClient("bank_e", "Bank E - Rural Community", "Community Banking", delay_seconds=2.0)
        }
        self.is_running = False
        self._thread: Optional[threading.Thread] = None

    def get_client(self, client_id: str) -> Optional[BankClient]:
        return self.clients.get(client_id)

    def set_status(self, client_id: str, status: str):
        if client_id in self.clients:
            self.clients[client_id].status = status

    def set_delay(self, client_id: str, delay_seconds: float):
        if client_id in self.clients:
            self.clients[client_id].delay_seconds = max(0.0, float(delay_seconds))

    def set_malicious(self, client_id: str, is_malicious: bool):
        if client_id in self.clients:
            self.clients[client_id].is_malicious = bool(is_malicious)

    def set_outdated(self, client_id: str, force_outdated: bool):
        if client_id in self.clients:
            self.clients[client_id].force_outdated = bool(force_outdated)

    def get_all_client_stats(self) -> List[Dict[str, Any]]:
        return [
            {
                "client_id": c.client_id,
                "client_name": c.name,
                "client_type": c.client_type,
                "status": c.status,
                "delay_seconds": c.delay_seconds,
                "is_malicious": c.is_malicious,
                "force_outdated": c.force_outdated,
                "current_snapshot_vid": c.current_snapshot_vid,
                "last_loss": round(float(c.last_loss), 4),
                "last_accuracy": round(float(c.last_accuracy), 4),
                "total_submissions": c.total_submissions,
                "successful_commits": c.successful_commits,
                "aborted_txns": c.aborted_txns,
                "last_submitted_at": c.last_submitted_at
            }
            for c in self.clients.values()
        ]
