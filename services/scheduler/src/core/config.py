from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator


class Settings(BaseSettings):
    # Service Configuration
    service_name: str = "scheduler"
    service_port: int = 3021
    log_level: str = "INFO"
    environment: str = "development"
    # Backwards-compatibility aliases
    app_name: str = "scheduler"
    app_version: str = "0.1.0"
    allowed_origins: List[str] = ["*"]

    # Database
    database_url: str
    database_pool_size: int = 20
    database_max_overflow: int = 10

    # Redis
    redis_url: str
    redis_password: Optional[str] = None
    redis_pool_size: int = 10

    # Service URLs
    ros_service_url: str
    gis_service_url: str
    flow_monitoring_url: str
    weather_service_url: str
    auth_service_url: str

    # JWT Configuration
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60

    # Optimization Settings
    optimization_timeout_seconds: int = 60
    max_parallel_optimizations: int = 5
    schedule_horizon_days: int = 7
    control_model_step_seconds: int = Field(default=300, gt=0)
    control_max_intermediate_trims: int = Field(default=1, ge=0, le=2)

    # Field Team Configuration
    max_operations_per_day: int = 30
    default_operation_time_minutes: int = 15
    travel_speed_kmh: float = 40.0

    # Real-time Monitoring
    gate_state_check_interval: int = 300  # 5 minutes
    deviation_threshold_percent: float = 10.0
    adaptation_cooldown_minutes: int = 15

    # Performance
    enable_cache: bool = True
    cache_ttl_seconds: int = 3600
    max_batch_size: int = 100

    # CORS
    cors_origins: List[str] = ["*"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v):
        if isinstance(v, str):
            return [i.strip() for i in v.split(",") if i.strip()]
        return v

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, v: str) -> str:
        if not isinstance(v, str):
            return v
        # Upgrade sync psycopg2 URL to asyncpg
        if v.startswith("postgresql://") and "+asyncpg" not in v:
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v


settings = Settings()
