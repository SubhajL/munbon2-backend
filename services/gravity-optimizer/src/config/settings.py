from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Service Info
    service_name: str = "gravity-optimizer"
    version: str = "1.0.0"
    port: int = 3020
    
    # Database Configuration
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "munbon_gis"
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    
    # Redis Configuration
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    
    # Physical Constants
    gravity: float = 9.81  # m/s^2
    water_density: float = 1000.0  # kg/m^3
    
    # Channel Parameters
    default_manning_n: float = 0.025  # Manning's roughness coefficient
    min_bed_slope: float = 0.0001  # Minimum bed slope
    max_bed_slope: float = 0.0002  # Maximum bed slope
    
    # Flow Constraints
    min_flow_depth: float = 0.3  # Minimum flow depth in meters
    max_flow_velocity: float = 2.0  # Maximum velocity to prevent erosion (m/s)
    min_flow_velocity: float = 0.3  # Minimum velocity to prevent sedimentation (m/s)
    
    # Safety Factors
    depth_safety_factor: float = 1.2  # Safety factor for minimum depth
    freeboard: float = 0.3  # Freeboard in meters
    
    # Optimization Parameters
    optimization_tolerance: float = 1e-6
    max_iterations: int = 1000
    convergence_threshold: float = 0.001
    
    # Zone Elevations (MSL in meters)
    source_elevation: float = 221.0
    zone_elevations: dict = {
        "zone_1": {"min": 218.0, "max": 219.0},
        "zone_2": {"min": 217.0, "max": 218.0},
        "zone_3": {"min": 217.0, "max": 217.5},
        "zone_4": {"min": 216.0, "max": 217.0},
        "zone_5": {"min": 215.0, "max": 216.0},
        "zone_6": {"min": 215.0, "max": 216.0}
    }
    
    # Gate Configuration
    automated_gates_count: int = 20
    manual_gates_count: int = 50  # Approximate
    
    # API Configuration
    api_prefix: str = "/api/v1/gravity-optimizer"
    cors_origins: list = ["*"]
    
    # Logging
    log_level: str = "INFO"
    
    class Config:
        env_prefix = "GRAVITY_"
        case_sensitive = False


settings = Settings()