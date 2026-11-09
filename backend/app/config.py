"""
Application configuration for the Adaptive MVCC AFL Transaction Coordinator.
"""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
DATA_DIR = BACKEND_DIR / "data"
WAL_DIR = DATA_DIR / "wal"
CHECKPOINTS_DIR = DATA_DIR / "checkpoints"
DATASETS_DIR = DATA_DIR / "datasets"

for directory in [DATA_DIR, WAL_DIR, CHECKPOINTS_DIR, DATASETS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

class Settings(BaseSettings):
    PROJECT_NAME: str = "Adaptive MVCC AFL Transaction Coordinator"
    API_V1_PREFIX: str = "/api/v1"
    
    # Database URL: Supports PostgreSQL (e.g. postgresql://postgres:postgres@localhost:5432/mvcc_fl)
    # or zero-config SQLite (sqlite:///.../metadata.db)
    DATABASE_URL: str = f"sqlite:///{DATA_DIR / 'catalog.db'}"
    
    # Custom DBMS Engine Defaults
    DEFAULT_STALENESS_THRESHOLD: int = 3
    MAX_STALENESS_ALLOWANCE: int = 6
    COSINE_SIMILARITY_THRESHOLD: float = 0.25
    
    # Priority Scheduler Weights
    WAITING_TIME_WEIGHT: float = 1.2
    STALENESS_PENALTY_WEIGHT: float = 0.8
    FAILURE_RECOVERY_WEIGHT: float = 1.5
    STARVATION_AGING_RATE: float = 0.5
    
    # WAL Configuration
    WAL_FILE_PATH: str = str(WAL_DIR / "active.wal")
    CHECKPOINT_INTERVAL_TXNS: int = 5
    
    # ML Hyperparameters
    FEATURE_DIM: int = 10
    LOCAL_EPOCHS: int = 3
    LEARNING_RATE: float = 0.05
    
    model_config = SettingsConfigDict(env_file=".env", extra="allow")

settings = Settings()
