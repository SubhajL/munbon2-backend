from typing import List
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # Service Configuration
    service_name: str = Field(default="flow-monitoring", env="SERVICE_NAME")
    port: int = Field(default=3011, env="PORT")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    environment: str = Field(default="development", env="ENVIRONMENT")
    
    # Database Connections
    influxdb_url: str = Field(..., env="INFLUXDB_URL")
    influxdb_token: str = Field(..., env="INFLUXDB_TOKEN")
    influxdb_org: str = Field(..., env="INFLUXDB_ORG")
    influxdb_bucket: str = Field(..., env="INFLUXDB_BUCKET")
    
    timescale_url: str = Field(..., env="TIMESCALE_URL")
    postgres_url: str = Field(..., env="POSTGRES_URL")
    
    # Redis Configuration
    redis_url: str = Field(..., env="REDIS_URL")
    
    # Kafka Configuration
    kafka_brokers: str = Field(..., env="KAFKA_BROKERS")
    kafka_topic_sensors: str = Field(..., env="KAFKA_TOPIC_SENSORS")
    kafka_topic_analytics: str = Field(..., env="KAFKA_TOPIC_ANALYTICS")
    kafka_consumer_group: str = Field(..., env="KAFKA_CONSUMER_GROUP")
    
    # Model Configuration
    model_update_interval: int = Field(default=300, env="MODEL_UPDATE_INTERVAL")
    anomaly_threshold: float = Field(default=3.0, env="ANOMALY_THRESHOLD")
    forecast_horizon: int = Field(default=24, env="FORECAST_HORIZON")
    
    # Performance Settings
    max_batch_size: int = Field(default=1000, env="MAX_BATCH_SIZE")
    batch_timeout_ms: int = Field(default=500, env="BATCH_TIMEOUT_MS")
    cache_ttl_seconds: int = Field(default=300, env="CACHE_TTL_SECONDS")
    
    # API Settings
    api_prefix: str = Field(default="/api/v1", env="API_PREFIX")
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:3001"],
        env="CORS_ORIGINS"
    )
    
    class Config:
        env_file = ".env"
        case_sensitive = False
    
    @property
    def kafka_brokers_list(self) -> List[str]:
        return self.kafka_brokers.split(",")
    
    @property
    def cors_origins_list(self) -> List[str]:
        if isinstance(self.cors_origins, str):
            return self.cors_origins.split(",")
        return self.cors_origins


settings = Settings()