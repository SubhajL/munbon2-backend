#!/usr/bin/env python3
"""
Test runner with mocked dependencies to avoid real database connections
"""

import os
import sys
import subprocess
from unittest.mock import MagicMock, patch

# Set test environment
os.environ['NODE_ENV'] = 'test'
os.environ['POSTGRES_URL'] = 'postgresql://test:test@localhost:5432/test'
os.environ['INFLUXDB_URL'] = 'http://localhost:8086'
os.environ['INFLUXDB_TOKEN'] = 'test-token'
os.environ['INFLUXDB_ORG'] = 'test-org'
os.environ['INFLUXDB_BUCKET'] = 'test-bucket'
os.environ['REDIS_URL'] = 'redis://localhost:6379/0'
os.environ['MONGODB_URL'] = 'mongodb://localhost:27017/test'
os.environ['KAFKA_BROKERS'] = 'localhost:9092'
os.environ['KAFKA_TOPIC_SENSORS'] = 'test-sensors'
os.environ['KAFKA_TOPIC_ANALYTICS'] = 'test-analytics'
os.environ['KAFKA_CONSUMER_GROUP'] = 'test-flow-monitoring'

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Mock database modules before they're imported
sys.modules['asyncpg'] = MagicMock()
sys.modules['psycopg2'] = MagicMock()
sys.modules['influxdb_client'] = MagicMock()
sys.modules['redis'] = MagicMock()
sys.modules['motor'] = MagicMock()
sys.modules['aiokafka'] = MagicMock()

# Run pytest with proper configuration
if __name__ == "__main__":
    # Set PYTHONPATH
    os.environ['PYTHONPATH'] = f"{os.getcwd()}/src:{os.getcwd()}"
    
    # Run pytest
    cmd = [
        sys.executable, 
        "-m", "pytest",
        "tests/",
        "-v",
        "--tb=short",
        "--no-header",
        "-p", "no:warnings"
    ]
    
    if len(sys.argv) > 1:
        cmd.extend(sys.argv[1:])
    
    print("Running Flow Monitoring Service Tests with Mocked Dependencies")
    print("=" * 60)
    
    result = subprocess.run(cmd)
    sys.exit(result.returncode)