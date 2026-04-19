"""
Production-grade configuration with environment-specific overrides.
Uses Pydantic BaseSettings for validation and type safety.
"""

from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from typing import Literal
from functools import lru_cache


class Settings(BaseSettings):
    """Base settings with dev/staging/production configurations."""
    
    # Environment & Mode
    env: Literal["dev", "staging", "production"] = Field(
        default="dev",
        description="Deployment environment"
    )
    log_level: str = Field(default="INFO", description="Python logging level")
    debug: bool = Field(default=False, description="Debug mode")
    
    # API Configuration
    api_title: str = Field(default="Voice Support Engine", description="API title")
    api_version: str = Field(default="1.0.0", description="API version")
    api_prefix: str = Field(default="/api/v1", description="API prefix")
    
    # Host & Port
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, description="Server port")
    
    # Security
    require_api_key: bool = Field(default=False, description="Enable API key requirement")
    api_key: str = Field(default="", description="API key for authentication")
    jwt_secret: str = Field(default="", description="JWT secret key")
    jwt_algorithm: str = Field(default="HS256", description="JWT algorithm")
    cors_origins: list = Field(default=["*"], description="CORS allowed origins")
    
    # Intent & Confidence
    confidence_threshold: float = Field(
        default=0.65,
        description="Minimum confidence threshold",
        ge=0.0,
        le=1.0
    )
    demo_user_id: int = Field(default=1, description="Demo user ID")
    
    # LLM Configuration
    llm_timeout_seconds: float = Field(
        default=3.0,
        description="LLM request timeout",
        gt=0.0
    )
    llm_max_retries: int = Field(default=3, description="LLM retry attempts")
    llm_backoff_factor: float = Field(default=0.5, description="Exponential backoff factor")
    google_api_key: str = Field(default="", description="Google Gemini API key")
    
    # Redis Configuration
    redis_host: str = Field(default="localhost", description="Redis host")
    redis_port: int = Field(default=6379, description="Redis port", ge=1, le=65535)
    redis_db: int = Field(default=0, description="Redis database", ge=0, le=15)
    redis_password: str = Field(default="", description="Redis password")
    redis_socket_timeout: float = Field(default=2.0, description="Redis socket timeout")
    redis_socket_connect_timeout: float = Field(default=2.0, description="Redis connection timeout")
    redis_connection_pool_size: int = Field(default=10, description="Redis connection pool size")
    redis_ttl_seconds: int = Field(default=3600, description="Redis default TTL")
    
    # Rate Limiting
    rate_limit_window_seconds: int = Field(
        default=60,
        description="Rate limit window in seconds",
        gt=0
    )
    rate_limit_max_requests: int = Field(
        default=100,
        description="Max requests per window",
        gt=0
    )
    rate_limit_enabled: bool = Field(default=True, description="Enable rate limiting")
    
    # Circuit Breaker
    circuit_breaker_enabled: bool = Field(default=True, description="Enable circuit breaker")
    circuit_breaker_failure_threshold: int = Field(default=5, description="Failures before opening")
    circuit_breaker_recovery_seconds: int = Field(default=60, description="Recovery timeout")
    
    # Tracing & Observability
    enable_tracing: bool = Field(default=False, description="Enable OpenTelemetry tracing")
    otel_exporter_endpoint: str = Field(default="http://localhost:4317", description="OTel exporter endpoint")
    prometheus_enabled: bool = Field(default=True, description="Enable Prometheus metrics")
    
    # Product API
    product_api_base_url: str = Field(default="http://localhost:9000", description="Product API base URL")
    product_api_timeout: float = Field(default=5.0, description="Product API timeout", gt=0)
    
    # Request/Response
    request_id_header: str = Field(default="x-request-id", description="Request ID header name")
    max_request_size_mb: int = Field(default=10, description="Max request payload size")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "allow"
    
    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v
    
    def is_production(self) -> bool:
        return self.env == "production"
    
    def is_staging(self) -> bool:
        return self.env == "staging"
    
    def is_dev(self) -> bool:
        return self.env == "dev"


class DevelopmentSettings(Settings):
    """Development-specific settings."""
    env: Literal["dev"] = "dev"
    debug: bool = True
    log_level: str = "DEBUG"
    require_api_key: bool = False
    cors_origins: list = ["*"]
    redis_host: str = "localhost"
    rate_limit_enabled: bool = False


class StagingSettings(Settings):
    """Staging-specific settings."""
    env: Literal["staging"] = "staging"
    debug: bool = False
    log_level: str = "INFO"
    require_api_key: bool = True
    cors_origins: list = Field(default=["https://staging.example.com"])


class ProductionSettings(Settings):
    """Production-specific settings."""
    env: Literal["production"] = "production"
    debug: bool = False
    log_level: str = "WARNING"
    require_api_key: bool = True
    cors_origins: list = Field(default=["https://example.com"])
    rate_limit_enabled: bool = True
    circuit_breaker_enabled: bool = True
    enable_tracing: bool = True


@lru_cache()
def get_settings() -> Settings:
    """Factory function to load settings based on ENV variable."""
    from functools import lru_cache
    import os
    
    settings_map = {
        "dev": DevelopmentSettings,
        "staging": StagingSettings,
        "production": ProductionSettings,
    }
    
    env = os.getenv("ENV", "dev").lower()
    settings_class = settings_map.get(env, DevelopmentSettings)
    
    return settings_class()
