from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import validator


class Settings(BaseSettings):
    # Service Configuration
    service_name: str = "scheduler"
    service_port: int = 3021
    log_level: str = "INFO"
    environment: str = "development"
    
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
    
    @validator("cors_origins", pre=True)
    def assemble_cors_origins(cls, v):
        if isinstance(v, str):
            return [i.strip() for i in v.split(",")]
        return v
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()