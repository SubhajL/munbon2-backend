import os
import contextlib
from config.settings import Settings

def test_env_mapping_uppercase_keys_resolved(monkeypatch):
    with contextlib.ExitStack() as stack:
        stack.enter_context(monkeypatch.context())
        monkeypatch.setenv("INFLUXDB_URL", "http://localhost:8086")
        monkeypatch.setenv("INFLUXDB_TOKEN", "token")
        monkeypatch.setenv("INFLUXDB_ORG", "org")
        monkeypatch.setenv("INFLUXDB_BUCKET", "bucket")
        monkeypatch.setenv("TIMESCALE_URL", "postgresql://u:p@localhost:5432/sensor_data")
        monkeypatch.setenv("POSTGRES_URL", "postgresql://u:p@localhost:5432/postgres")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/3")
        monkeypatch.setenv("KAFKA_BROKERS", "localhost:9092")
        monkeypatch.setenv("KAFKA_TOPIC_SENSORS", "sensor-data")
        monkeypatch.setenv("KAFKA_TOPIC_ANALYTICS", "flow-analytics")
        monkeypatch.setenv("KAFKA_CONSUMER_GROUP", "flow-monitoring-consumer")

        s = Settings()
        assert s.influxdb_url == "http://localhost:8086"
        assert s.influxdb_bucket == "bucket"
        assert s.timescale_url.endswith("/sensor_data")
        assert s.postgres_url.endswith("/postgres")
        assert s.redis_url.startswith("redis://")
