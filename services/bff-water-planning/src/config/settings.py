from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    # Service Configuration
    service_name: str = "bff-water-planning"
    port: int = 4002  # Corrected port for Water Planning BFF
    host: str = "0.0.0.0"
    environment: str = Field(default="development", env="ENVIRONMENT")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    
    # API Configuration
    api_prefix: str = "/api/v1"
    cors_origins: str = Field(default="*", env="CORS_ORIGINS")
    
    # Database Connections
    postgres_url: str = Field(
        default="postgresql://postgres:postgres@localhost:5434/munbon_dev",
        env="POSTGRES_URL"
    )
    redis_url: str = Field(
        default="redis://localhost:6379/2",
        env="REDIS_URL"
    )
    
    # External Service URLs
    flow_monitoring_url: str = Field(
        default="http://localhost:3014",  # Corrected port for Flow Monitoring
        env="FLOW_MONITORING_URL"
    )
    scheduler_url: str = Field(
        default="http://localhost:3021",
        env="SCHEDULER_URL"
    )
    ros_service_url: str = Field(
        default="http://localhost:3047",  # Correct ROS port
        env="ROS_SERVICE_URL"
    )
    gis_service_url: str = Field(
        default="http://localhost:3007",  # GIS service correct port
        env="GIS_SERVICE_URL"
    )
    weather_api_url: str = Field(
        default="https://api.weather.example.com",
        env="WEATHER_API_URL"
    )
    weather_service_url: str = Field(
        default="http://localhost:3006",  # Weather service
        env="WEATHER_SERVICE_URL"
    )
    awd_control_url: str = Field(
        default="http://localhost:3013",  # Corrected port for AWD Control Service
        env="AWD_CONTROL_URL"
    )
    sensor_data_url: str = Field(
        default="http://localhost:3003",  # Sensor Data Service
        env="SENSOR_DATA_URL"
    )
    
    # Mock server for development
    use_mock_server: bool = Field(default=False, env="USE_MOCK_SERVER")
    mock_server_url: str = Field(
        default="http://localhost:3099",
        env="MOCK_SERVER_URL"
    )
    
    # Spatial Configuration
    default_srid: int = 4326  # WGS84
    utm_zone: int = 48  # Thailand UTM Zone
    
    # Database Pool Configuration
    db_pool_min_size: int = Field(default=10, env="DB_POOL_MIN_SIZE")
    db_pool_max_size: int = Field(default=20, env="DB_POOL_MAX_SIZE")
    db_pool_max_queries: int = Field(default=50000, env="DB_POOL_MAX_QUERIES")
    db_pool_max_inactive_connection_lifetime: int = Field(default=300, env="DB_POOL_MAX_INACTIVE_LIFETIME")
    
    # Cache Configuration
    cache_ttl_seconds: int = 300  # 5 minutes
    demand_cache_ttl: int = 3600  # 1 hour
    
    # Demand Aggregation Settings
    min_demand_m3: float = 100  # Minimum demand to process
    max_sections_per_gate: int = 10  # Maximum sections sharing a gate
    demand_advance_hours: int = 24  # Submit demands 24hrs in advance
    
    # Priority Weights
    crop_stage_weight: float = 0.4
    moisture_deficit_weight: float = 0.3
    economic_value_weight: float = 0.2
    stress_indicator_weight: float = 0.1
    
    # Flow Monitoring Network Configuration
    flow_monitoring_network_file: Optional[str] = Field(
        default=None,
        env="FLOW_MONITORING_NETWORK_FILE",
        description="Path to canal network JSON file"
    )
    
    # Demand Calculation Configuration
    demand_combination_strategy: str = Field(
        default="aquacrop_priority",
        env="DEMAND_COMBINATION_STRATEGY",
        description="Strategy for combining ROS and AquaCrop demands"
    )
    
    # Scheduler Service Configuration
    scheduler_service_url: str = Field(
        default="http://localhost:3021",
        env="SCHEDULER_SERVICE_URL"
    )
    
    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]
    
    @property
    def external_service_url(self) -> str:
        """Get appropriate service URL based on mock server setting"""
        return self.mock_server_url if self.use_mock_server else self.flow_monitoring_url
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )


settings = Settings()