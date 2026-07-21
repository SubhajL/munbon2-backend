from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    # Service Configuration
    service_name: str = Field(default="flow-monitoring", env="SERVICE_NAME")
    port: int = Field(default=3011, env="PORT")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    environment: str = Field(default="development", env="ENVIRONMENT")
    # Wave 1.5 (Decision 2): the legacy /api/v1/gates/* dual-stack stays OFF unless
    # explicitly enabled; it is quarantined until the F-02 SCADA bridge replaces it.
    gates_api_enabled: bool = Field(default=False, env="GATES_API_ENABLED")

    # Database Connections
    influxdb_url: str = Field(..., env="INFLUXDB_URL")
    influxdb_token: str = Field(..., env="INFLUXDB_TOKEN")
    influxdb_org: str = Field(..., env="INFLUXDB_ORG")
    influxdb_bucket: str = Field(..., env="INFLUXDB_BUCKET")

    timescale_url: str = Field(..., env="TIMESCALE_URL")
    postgres_url: str = Field(..., env="POSTGRES_URL")

    # Redis Configuration
    redis_url: str = Field(..., env="REDIS_URL")

    # Kafka Configuration (optional; service runs without Kafka)
    kafka_brokers: Optional[str] = Field(default=None, env="KAFKA_BROKERS")
    kafka_topic_sensors: Optional[str] = Field(default=None, env="KAFKA_TOPIC_SENSORS")
    kafka_topic_analytics: Optional[str] = Field(
        default=None, env="KAFKA_TOPIC_ANALYTICS"
    )
    kafka_consumer_group: Optional[str] = Field(
        default=None, env="KAFKA_CONSUMER_GROUP"
    )

    # Model Configuration
    hydraulic_model_release_path: Optional[str] = Field(
        default=None, env="HYDRAULIC_MODEL_RELEASE_PATH"
    )
    commandability_approval_path: Optional[str] = Field(
        default=None, env="HYDRAULIC_COMMANDABILITY_APPROVAL_PATH"
    )
    # PR 4.4b-1: the committed prediction-engine descriptor. When unset, main.py
    # resolves the tracked data/prediction-engine/prediction-engine-v1.json.
    prediction_engine_descriptor_path: Optional[str] = Field(
        default=None, env="PREDICTION_ENGINE_DESCRIPTOR_PATH"
    )
    # Identity rollout mode: accept-v1-write-v2 (default) | require-v2.
    prediction_identity_rollout_mode: str = Field(
        default="accept-v1-write-v2", env="PREDICTION_IDENTITY_ROLLOUT_MODE"
    )
    model_update_interval: int = Field(default=300, env="MODEL_UPDATE_INTERVAL")
    anomaly_threshold: float = Field(default=3.0, env="ANOMALY_THRESHOLD")
    forecast_horizon: int = Field(default=24, env="FORECAST_HORIZON")

    # Performance Settings
    max_batch_size: int = Field(default=1000, env="MAX_BATCH_SIZE")
    batch_timeout_ms: int = Field(default=500, env="BATCH_TIMEOUT_MS")
    cache_ttl_seconds: int = Field(default=300, env="CACHE_TTL_SECONDS")

    # API Settings
    api_prefix: str = Field(default="/api/v1", env="API_PREFIX")
    cors_origins: str = Field(
        default="http://localhost:3000,http://localhost:3001", env="CORS_ORIGINS"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
        protected_namespaces=("settings_",),
    )

    @property
    def kafka_brokers_list(self) -> List[str]:
        if not self.kafka_brokers:
            return []
        return [broker.strip() for broker in self.kafka_brokers.split(",")]

    @property
    def cors_origins_list(self) -> List[str]:
        if not self.cors_origins:
            return []
        if isinstance(self.cors_origins, str):
            return [origin.strip() for origin in self.cors_origins.split(",")]
        return self.cors_origins


settings = Settings()
