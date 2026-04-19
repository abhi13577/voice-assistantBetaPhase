import os

CONFIDENCE_THRESHOLD = float(
    os.getenv("CONFIDENCE_THRESHOLD", "0.65")
)

DEMO_USER_ID = int(
    os.getenv("DEMO_USER_ID", "1")
)

API_URL = os.getenv(
    "VOICE_API_URL",
    "http://localhost:8000"
)

ENV = os.getenv("ENV", "dev").lower()
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

REQUIRE_API_KEY = os.getenv("REQUIRE_API_KEY", "false").lower() == "true"
API_KEY = os.getenv("VOICE_API_KEY", "")

RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "5"))
RATE_LIMIT_MAX_REQUESTS = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "10"))

LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "3.0"))