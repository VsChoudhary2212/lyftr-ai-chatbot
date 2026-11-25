
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from project root
ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")

# Primary provider: Groq
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()

GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "groq/openai/gpt-oss-20b"
)

# Fallback provider: Gemini
GEMINI_MODEL = os.getenv(
    "MODEL_NAME",
    "gemini/gemini-3.8-flash"
)

LLM_API_KEYS = [
    key.strip()
    for key in os.getenv("LLM_API_KEYS", "").split(",")
    if key.strip()
]

# Database
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./app.db"
)

# CORS
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:5173"
    ).split(",")
    if origin.strip()
]

# Failure simulation
ENABLE_FAILURE_SIMULATION = (
    os.getenv("ENABLE_FAILURE_SIMULATION", "false").lower()
    == "true"
)

# Default system prompt
DEFAULT_SYSTEM_PROMPT = (
    "You are Lyftr AI, a helpful, accurate and friendly AI assistant. "
    "Give clear, structured and useful answers."
)
