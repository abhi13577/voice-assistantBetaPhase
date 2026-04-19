import redis
import json
import hashlib
import logging
from app.core.config import REDIS_HOST, REDIS_PORT

logger = logging.getLogger(__name__)

class CacheService:

    def __init__(self):
        self.client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            decode_responses=True,
            socket_timeout=1,
            socket_connect_timeout=1
        )

    # ✅ CHANGE 4 — NORMALIZE CACHE KEY (Fixed)
    def _generate_key(self, text: str):
        normalized = text.strip().lower()
        return hashlib.sha256(normalized.encode()).hexdigest()

    def get(self, text: str):
        key = self._generate_key(text)

        try:
            data = self.client.get(key)

            if data:
                logger.info(f"[CACHE HIT] key={key}")
                return json.loads(data)

            logger.info(f"[CACHE MISS] key={key}")

        except Exception as e:
            logger.warning(f"Redis GET failed: {e}")

        return None

    def ping(self) -> bool:
        try:
            return bool(self.client.ping())
        except Exception as e:
            logger.warning(f"Redis PING failed: {e}")
            return False

    # ✅ CHANGE 5 — ADD TTL SUPPORT (Full function replaced)
    def set(self, text: str, value, ttl=3600):
        key = self._generate_key(text)

        try:
            self.client.setex(
                key,
                ttl,
                json.dumps(value)
            )
            logger.info(f"[CACHE SET] key={key} TTL={ttl}")

        except Exception as e:
            logger.warning(f"Redis SET failed: {e}")

cache_service = CacheService()