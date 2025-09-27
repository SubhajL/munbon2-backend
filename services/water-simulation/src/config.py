"""
Configuration settings for Water Simulation Service
"""

import os
from typing import Optional
from pydantic import BaseSettings, PostgresDsn, validator
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings with validation"""
    
    # Service Info
    service_name: str = "Water Simulation Service"
    version: str = "1.0.0"
    api_prefix: str = "/api/v1"
    
    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8090
    workers: int = 4
    
    # Database Configuration
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_db: str = "water_simulation"
    
    # Service URLs
    ros_service_url: str = "http://localhost:8001"
    flow_service_url: str = "http://localhost:8002"
    gate_service_url: str = "http://localhost:8003"
    gis_service_url: str = "http://localhost:8004"
    
    # Simulation Settings
    simulation_time_step_minutes: int = 60  # 1 hour default
    max_simulation_days: int = 365
    optimization_max_iterations: int = 1000
    optimization_convergence_threshold: float = 0.001
    
    # Cache Settings
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 1
    
    # Logging
    log_level: str = "INFO"
    
    @validator("postgres_port", "redis_port", "port")
    def validate_port(cls, v):
        if not 1 <= v <= 65535:
            raise ValueError("Port must be between 1 and 65535")
        return v
    
    @property
    def database_url(self) -> str:
        """Construct database URL"""
        return f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
    
    @property
    def redis_url(self) -> str:
        """Construct Redis URL"""
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"
    
    class Config:
        env_prefix = "SIMULATION_"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


# Constants for simulation
SIMULATION_STATUS = {
    "PENDING": "pending",
    "RUNNING": "running",
    "COMPLETED": "completed",
    "FAILED": "failed",
    "CANCELLED": "cancelled"
}

OPTIMIZATION_OBJECTIVES = {
    "WATER_EFFICIENCY": "water_efficiency",
    "FAIRNESS": "fairness",
    "ENERGY_MINIMAL": "energy_minimal",
    "MULTI_OBJECTIVE": "multi_objective"
}

GATE_OPERATION_MODES = {
    "AUTOMATIC": "automatic",
    "MANUAL": "manual",
    "MAINTENANCE": "maintenance"
}