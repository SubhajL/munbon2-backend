"""Configuration settings for Water Accounting Service"""

from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional

class Settings(BaseSettings):
    """Application settings"""
    
    # Service Configuration
    SERVICE_NAME: str = "water-accounting-service"
    SERVICE_PORT: int = 3024
    DEBUG: bool = True
    
    # Database Configuration
    DATABASE_HOST: str = "localhost"
    DATABASE_PORT: int = 5432
    DATABASE_NAME: str = "munbon_water_accounting"
    DATABASE_USER: str = "water_accounting_user"
    DATABASE_PASSWORD: str = "water_accounting_pass"
    
    # TimescaleDB Configuration
    TIMESCALE_HOST: str = "localhost"
    TIMESCALE_PORT: int = 5433
    TIMESCALE_NAME: str = "munbon_timeseries"
    TIMESCALE_USER: str = "timescale_user"
    TIMESCALE_PASSWORD: str = "timescale_pass"
    
    # Integration Points
    SENSOR_DATA_SERVICE_URL: str = "http://localhost:3003"
    GIS_SERVICE_URL: str = "http://localhost:3007"
    WEATHER_SERVICE_URL: str = "http://localhost:3008"
    SCADA_SERVICE_URL: str = "http://localhost:3023"
    FLOW_MONITORING_URL: str = "http://localhost:3016/api/v1"
    SCHEDULER_URL: str = "http://localhost:3017/api/v1"
    MOCK_SERVER_URL: str = "http://localhost:3099/api/v1"
    
    # Security
    SECRET_KEY: str = "water-accounting-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    
    # Metrics
    ENABLE_METRICS: bool = True
    METRICS_PORT: int = 9024
    
    # Water Accounting Specific Settings
    DEFAULT_SEEPAGE_RATE: float = 0.02  # 2% per km
    DEFAULT_EVAPORATION_RATE: float = 0.005  # 0.5% per hour
    MINIMUM_EFFICIENCY_THRESHOLD: float = 0.70  # 70% minimum efficiency
    DEFICIT_CARRY_FORWARD_WEEKS: int = 4  # Carry deficits for 4 weeks
    
    @property
    def DATABASE_URL(self) -> str:
        """PostgreSQL connection URL"""
        return f"postgresql+asyncpg://{self.DATABASE_USER}:{self.DATABASE_PASSWORD}@{self.DATABASE_HOST}:{self.DATABASE_PORT}/{self.DATABASE_NAME}"
    
    @property
    def TIMESCALE_URL(self) -> str:
        """TimescaleDB connection URL"""
        return f"postgresql+asyncpg://{self.TIMESCALE_USER}:{self.TIMESCALE_PASSWORD}@{self.TIMESCALE_HOST}:{self.TIMESCALE_PORT}/{self.TIMESCALE_NAME}"
    
    class Config:
        env_file = ".env"
        case_sensitive = True

@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()