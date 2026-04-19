from prometheus_client import Counter, Histogram

# total API requests
voice_requests_total = Counter(
    "voice_requests_total",
    "Total number of voice requests"
)

# request errors
voice_errors_total = Counter(
    "voice_errors_total",
    "Total number of voice processing errors"
)

# request latency
voice_request_latency_seconds = Histogram(
    "voice_request_latency_seconds",
    "Latency of voice requests"
)

# LLM calls
llm_requests_total = Counter(
    "llm_requests_total",
    "Total number of LLM calls"
)

# Redis cache metrics
redis_cache_hits_total = Counter(
    "redis_cache_hits_total",
    "Total Redis cache hits"
)

redis_cache_misses_total = Counter(
    "redis_cache_misses_total",
    "Total Redis cache misses"
)