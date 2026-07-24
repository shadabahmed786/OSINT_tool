import os
from pathlib import Path

# Base Directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Database Settings
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "osint_platform.db"

# Evidence & Screenshot Storage
EVIDENCE_DIR = DATA_DIR / "evidence"
EVIDENCE_DIR.mkdir(exist_ok=True)

# HTTP Request Defaults
REQUEST_TIMEOUT = 10.0  # seconds
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# Guardrail Enforcer (§0): Hard-fail if any cloud AI or paid breach API keys are detected
FORBIDDEN_API_KEYS = [
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "DEHASHED_API_KEY",
    "INTELX_API_KEY",
    "HIBP_API_KEY",
    "PINEYES_API_KEY",
    "FACECHECK_API_KEY",
]

detected_keys = [k for k in FORBIDDEN_API_KEYS if os.getenv(k)]
if detected_keys:
    raise RuntimeError(
        f"CRITICAL GUARDRAIL VIOLATION (§0): Forbidden API keys detected in environment: {', '.join(detected_keys)}. "
        "This platform operates strictly local-first with keyless open endpoints. Cloud and paid API integrations are forbidden."
    )

# Data Retention Settings (§0, §3)
RETENTION_DAYS_DEFAULT = 90

# Rate Limiting & Pacing Defaults (§0)
RATE_LIMIT_DELAY_SECONDS = 0.5

# Local AI Endpoints (strictly on-device via Ollama/llama.cpp) (§0, §5, §7)
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
DEFAULT_TEXT_MODEL = "llama3.1:8b"
DEFAULT_VISION_MODEL = "qwen2.5-vl:7b"
DEFAULT_EMBED_MODEL = "bge-small-en-v1.5"

