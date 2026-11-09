"""
Fraud Detection Neural Network and Vectorized Model Weight Utilities.
Supports PyTorch model architecture with flat numpy vector conversion for
atomic delta computation, differential logging, and OCC validation.
"""
from typing import Dict, Tuple
import numpy as np
import torch
import torch.nn as nn
from app.config import settings

class FraudDetectionNN(nn.Module):
    """Small fraud detection classification neural network."""
    def __init__(self, input_dim: int = settings.FEATURE_DIM):
        super().__init__()
        self.fc1 = nn.Linear(input_dim, 16)
        self.relu1 = nn.ReLU()
        self.dropout = nn.Dropout(0.1)
        self.fc2 = nn.Linear(16, 8)
        self.relu2 = nn.ReLU()
        self.out = nn.Linear(8, 1)
        
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.relu1(self.fc1(x))
        x = self.dropout(x)
        x = self.relu2(self.fc2(x))
        return self.out(x)

def get_flat_params(model: nn.Module) -> np.ndarray:
    """Flattens all trainable parameters into a single 1D numpy float32 vector."""
    params = []
    for p in model.parameters():
        params.append(p.detach().cpu().numpy().flatten())
    return np.concatenate(params).astype(np.float32)

def set_flat_params(model: nn.Module, flat_params: np.ndarray):
    """Restores model parameters from a flat 1D numpy vector."""
    offset = 0
    with torch.no_grad():
        for p in model.parameters():
            numel = p.numel()
            chunk = flat_params[offset : offset + numel]
            p.copy_(torch.from_numpy(chunk.reshape(p.shape)))
            offset += numel

def compute_model_metrics(model: nn.Module, X: np.ndarray, y: np.ndarray) -> Tuple[float, float]:
    """Computes binary cross entropy loss and classification accuracy."""
    model.eval()
    with torch.no_grad():
        tensor_X = torch.tensor(X, dtype=torch.float32)
        tensor_y = torch.tensor(y, dtype=torch.float32).unsqueeze(1)
        logits = model(tensor_X)
        loss = nn.BCEWithLogitsLoss()(logits, tensor_y).item()
        preds = (torch.sigmoid(logits) >= 0.5).float()
        acc = (preds == tensor_y).float().mean().item()
    return float(loss), float(acc)

def get_initial_weights() -> np.ndarray:
    """Returns initialized reproducible baseline weights."""
    torch.manual_seed(1337)
    model = FraudDetectionNN()
    return get_flat_params(model)
