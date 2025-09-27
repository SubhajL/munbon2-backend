"""
Test configuration for real service integration
"""
import os
from typing import Optional
from pydantic import BaseSettings


class TestServiceEndpoints(BaseSettings):
    """Configuration for real service endpoints in tests"""
    
    # ROS Service
    ros_base_url: str = os.getenv("TEST_ROS_URL", "http://localhost:8004")
    
    # Flow Monitoring Service
    flow_base_url: str = os.getenv("TEST_FLOW_URL", "http://localhost:8005")
    
    # Gate Control Service
    gate_base_url: str = os.getenv("TEST_GATE_URL", "http://localhost:8006")
    
    # GIS Service
    gis_base_url: str = os.getenv("TEST_GIS_URL", "http://localhost:8007")
    
    # Database URLs
    postgres_url: str = os.getenv(
        "TEST_DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/munbon_test"
    )
    
    # Test mode selection
    use_real_services: bool = os.getenv("USE_REAL_SERVICES", "false").lower() == "true"
    
    # Service timeouts
    service_timeout_seconds: int = 30
    
    # Test data configuration
    test_zone_id: int = 1
    test_section_ids: list[str] = ["Zone_1_Section_A", "Zone_1_Section_B"]
    test_gate_ids: list[str] = ["GATE001", "GATE002", "GATE003"]
    test_crop_type: str = "rice"
    
    # Authentication tokens if needed
    ros_auth_token: Optional[str] = os.getenv("TEST_ROS_AUTH_TOKEN")
    flow_auth_token: Optional[str] = os.getenv("TEST_FLOW_AUTH_TOKEN")
    
    class Config:
        env_file = ".env.test"


test_config = TestServiceEndpoints()