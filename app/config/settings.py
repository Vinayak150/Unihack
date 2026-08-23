"""Central configuration, loaded from environment (.env supported)."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


class Settings:
    APP_MODE: str = os.getenv("APP_MODE", "mock")  # "mock" | "claude"
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5")
    CLAUDE_MODEL_FAST: str = os.getenv("CLAUDE_MODEL_FAST", os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5"))

    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))

    DATA_DIR: Path = Path(os.getenv("DATA_DIR", str(ROOT / "data")))
    REFERENCE_DIR: Path = DATA_DIR / "reference"
    EXTERNAL_REFERENCE_DIR: Path = REFERENCE_DIR / "external"
    CACHE_DIR: Path = DATA_DIR / "cache"
    RAW_DIR: Path = DATA_DIR / "raw"
    REPORTS_DIR: Path = Path(os.getenv("REPORTS_DIR", str(ROOT / "reports")))

    REVIEW_CONFIDENCE_THRESHOLD: float = float(os.getenv("REVIEW_CONFIDENCE_THRESHOLD", "0.72"))

    PIPELINE_VERSION: str = "0.1.0"
    SCHEMA_VERSION: str = "unilog-delivery-format-252"
    TAXONOMY_VERSION: str = "seed-2026.1"
    LOV_VERSION: str = "seed-2026.1"
    UOM_VERSION: str = "seed-2026.1"

    GROUND_TRUTH_CSV: Path = RAW_DIR / "ground_truth_delivery_format.csv"
    SAMPLE_INPUT_CSV: Path = RAW_DIR / "sample_1000_items_input.csv"


settings = Settings()
settings.CACHE_DIR.mkdir(parents=True, exist_ok=True)
settings.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
