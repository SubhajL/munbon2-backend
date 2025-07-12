"""Configuration management for Munbon services."""

from typing import Optional, Type, TypeVar
from pydantic import BaseSettings, Field, validator
from functools import lru_cache

T = TypeVar("T", bound="Config")


class Config(BaseSettings):
    """Base configuration with common settings."""
    
    # Environment
    environment: str = Field(
        default="development",
        env="ENVIRONMENT",
        description="Application environment"
    )
    
    # Service
    service_name: str = Field(
        ...,
        env="SERVICE_NAME",
        description="Name of the microservice"
    )
    port: int = Field(
        default=8000,
        env="PORT",
        description="Service port"
    )
    
    # Logging
    log_level: str = Field(
        default="INFO",
        env="LOG_LEVEL",
        description="Logging level"
    )
    
    # Database
    database_url: Optional[str] = Field(
        default=None,
        env="DATABASE_URL",
        description="Database connection URL"
    )
    
    # Redis
    redis_url: Optional[str] = Field(
        default=None,
        env="REDIS_URL",
        description="Redis connection URL"
    )
    
    # Message Queue
    rabbitmq_url: Optional[str] = Field(
        default=None,
        env="RABBITMQ_URL",
        description="RabbitMQ connection URL"
    )
    kafka_brokers: Optional[str] = Field(
        default=None,
        env="KAFKA_BROKERS",
        description="Kafka brokers (comma-separated)"
    )
    
    # Authentication
    jwt_secret: str = Field(
        default="dev-secret",
        env="JWT_SECRET",
        description="JWT signing secret"
    )
    jwt_algorithm: str = Field(
        default="HS256",
        env="JWT_ALGORITHM",
        description="JWT algorithm"
    )
    jwt_expiry_hours: int = Field(
        default=24,
        env="JWT_EXPIRY_HOURS",
        description="JWT expiry in hours"
    )
    
    # Monitoring
    prometheus_enabled: bool = Field(
        default=True,
        env="PROMETHEUS_ENABLED",
        description="Enable Prometheus metrics"
    )
    jaeger_endpoint: Optional[str] = Field(
        default=None,
        env="JAEGER_ENDPOINT",
        description="Jaeger tracing endpoint"
    )
    
    # Rate limiting
    rate_limit_enabled: bool = Field(
        default=True,
        env="RATE_LIMIT_ENABLED",
        description="Enable rate limiting"
    )
    rate_limit_requests: int = Field(
        default=100,
        env="RATE_LIMIT_REQUESTS",
        description="Max requests per window"
    )
    rate_limit_window: int = Field(
        default=900,  # 15 minutes
        env="RATE_LIMIT_WINDOW",
        description="Rate limit window in seconds"
    )
    
    @validator("environment")
    def validate_environment(cls, v: str) -> str:
        """Validate environment value."""
        allowed = ["development", "testing", "staging", "production"]
        if v not in allowed:
            raise ValueError(f"Environment must be one of {allowed}")
        return v
    
    @validator("log_level")
    def validate_log_level(cls, v: str) -> str:
        """Validate log level."""
        allowed = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v = v.upper()
        if v not in allowed:
            raise ValueError(f"Log level must be one of {allowed}")
        return v
    
    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.environment == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.environment == "development"
    
    class Config:
        """Pydantic config."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_config(config_class: Type[T] = Config) -> T:
    """
    Get configuration instance (cached).
    
    Args:
        config_class: Configuration class to instantiate
        
    Returns:
        Configuration instance
    """
    return config_class()  # type: ignore