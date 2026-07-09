import pytest

from config.settings import Settings


def _base_settings_payload() -> dict[str, str]:
    return {
        "influxdb_url": "http://localhost:8086",
        "influxdb_token": "token",
        "influxdb_org": "munbon",
        "influxdb_bucket": "flow_monitoring",
        "timescale_url": "postgresql://example",
        "postgres_url": "postgresql://example",
        "redis_url": "redis://localhost:6379/3",
        "kafka_brokers": "broker:9092",
        "kafka_topic_sensors": "sensor-data",
        "kafka_topic_analytics": "flow-analytics",
        "kafka_consumer_group": "flow-monitoring-consumer",
        "cors_origins": "http://a.example,http://b.example",
    }


def test_settings_parses_comma_separated_cors_origins():
    payload = _base_settings_payload()
    settings = Settings.model_validate(payload)

    assert settings.cors_origins_list == [
        "http://a.example",
        "http://b.example",
    ]


def test_settings_ignores_unknown_environment_keys():
    payload = _base_settings_payload()
    payload["unused_key"] = "value"

    settings = Settings.model_validate(payload)

    assert not hasattr(settings, "unused_key")
