"""Shared configuration for the AROL Customer Platform backend."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATASET_DIR = PROJECT_ROOT / "Project-Q2-DataBase"
MANUALS_DIR = DATASET_DIR / "manuals"
DATASET_XLSX = DATASET_DIR / "AROL_Q2_synthetic_fleet_dataset.xlsx"

DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "arol.db"
INDEX_PATH = DATA_DIR / "manual_index.pkl"

# Language model: any OpenAI-compatible API (see README). We use Cerebras.
LLM_MODEL = os.getenv("LLM_MODEL", "qwen-3.8-27b")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.cerebras.ai/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
# Seconds to wait for one model call. Free-tier requests sometimes hang, and
# retrying is quicker than waiting. Raise it for a local model, they are slower.
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "6"))

# The dataset stops on 2026-08-04, so its README asks to use the next day as "today".
TODAY = os.getenv("TODAY", "2026-08-05")

# The dataset has no passwords, so load_data.py gives every account this one.
DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "arol2026")

# Base URL written into the QR codes (the frontend).
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
