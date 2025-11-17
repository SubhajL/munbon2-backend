import json
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    # Service Configuration
    service_name: str = Field(default="scheduler", env="SERVICE_NAME")
    port: int = Field(default=3021, env="PORT")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    environment: str = Field(default="development", env="ENVIRONMENT")
    
    # Database Connections
    postgres_url: str = Field(..., env="POSTGRES_URL")
    redis_url: str = Field(..., env="REDIS_URL")
    
    # External Services
    flow_monitoring_url: str = Field(
        default="http://localhost:3011", 
        env="FLOW_MONITORING_URL"
    )
    ros_gis_url: str = Field(
        default="http://localhost:3041", 
        env="ROS_GIS_URL"
    )
    weather_api_url: str = Field(..., env="WEATHER_API_URL")
    sms_gateway_url: str = Field(..., env="SMS_GATEWAY_URL")
    
    # Schedule Configuration
    schedule_horizon_days: int = Field(default=7, env="SCHEDULE_HORIZON_DAYS")
    min_gate_travel_time_minutes: int = Field(default=30, env="MIN_GATE_TRAVEL_TIME")
    max_daily_operations_per_team: int = Field(default=20, env="MAX_DAILY_OPS_PER_TEAM")
    field_work_start_hour: int = Field(default=7, env="FIELD_WORK_START_HOUR")
    field_work_end_hour: int = Field(default=17, env="FIELD_WORK_END_HOUR")
    
    # Optimization Parameters
    optimization_time_limit_seconds: int = Field(default=30, env="OPTIMIZATION_TIME_LIMIT")
    demand_satisfaction_weight: float = Field(default=0.7, env="DEMAND_WEIGHT")
    travel_minimization_weight: float = Field(default=0.2, env="TRAVEL_WEIGHT")
    balance_weight: float = Field(default=0.1, env="BALANCE_WEIGHT")
    
    # Field Teams Configuration
    field_teams: str = Field(
        default="Team_A,Team_B",
        env="FIELD_TEAMS"
    )
    team_base_locations: dict = Field(
        default={
            "Team_A": {"lat": 14.8200, "lon": 103.1500},
            "Team_B": {"lat": 14.8300, "lon": 103.1600}
        }
    )

    # Real-time Adaptation
    monitoring_interval_seconds: int = Field(default=300, env="MONITORING_INTERVAL")
    flow_deviation_threshold: float = Field(default=0.1, env="FLOW_DEVIATION_THRESHOLD")
    schedule_update_cooldown_minutes: int = Field(default=60, env="SCHEDULE_UPDATE_COOLDOWN")

    # API Settings
    api_prefix: str = Field(default="/api/v1", env="API_PREFIX")
    cors_origins: str = Field(
        default="http://localhost:3000,http://localhost:3001",
        env="CORS_ORIGINS"
    )

    # Mobile App Configuration
    mobile_sync_batch_size: int = Field(default=50, env="MOBILE_SYNC_BATCH_SIZE")
    offline_data_retention_days: int = Field(default=30, env="OFFLINE_RETENTION_DAYS")
    schedule_cache_ttl: int = Field(default=600, env="SCHEDULE_CACHE_TTL")
    job_cleanup_retention_days: int = Field(default=7, env="JOB_CLEANUP_RETENTION_DAYS")

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore"
    )

    @property
    def cors_origins_list(self) -> List[str]:
        return self._parse_comma_separated(self.cors_origins)

    @property
    def field_teams_list(self) -> List[str]:
        return self._parse_comma_separated(self.field_teams)

    @staticmethod
    def _parse_comma_separated(value: str) -> List[str]:
        if not value:
            return []
        stripped = value.strip()
        if stripped.startswith('['):
            try:
                parsed = json.loads(stripped)
                return [str(item).strip() for item in parsed if str(item).strip()]
            except json.JSONDecodeError:
                pass
        return [item.strip() for item in stripped.split(",") if item.strip()]


settings = Settings()
