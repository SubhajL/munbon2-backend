#!/bin/bash

# Kafka topic creation script for Munbon Irrigation System
# This script creates all required Kafka topics with appropriate configurations

KAFKA_CONTAINER="munbon-kafka"
KAFKA_BOOTSTRAP_SERVER="kafka:29092"

# Function to create a topic
create_topic() {
    local TOPIC_NAME=$1
    local PARTITIONS=$2
    local REPLICATION_FACTOR=$3
    local CONFIG=$4
    
    echo "Creating topic: $TOPIC_NAME"
    docker exec $KAFKA_CONTAINER kafka-topics \
        --create \
        --bootstrap-server $KAFKA_BOOTSTRAP_SERVER \
        --topic $TOPIC_NAME \
        --partitions $PARTITIONS \
        --replication-factor $REPLICATION_FACTOR \
        $CONFIG \
        --if-not-exists
}

# Wait for Kafka to be ready
echo "Waiting for Kafka to be ready..."
sleep 10

# Sensor data topics
create_topic "sensor.water-level" 6 1 "--config retention.ms=2592000000 --config compression.type=lz4"
create_topic "sensor.moisture" 6 1 "--config retention.ms=2592000000 --config compression.type=lz4"
create_topic "sensor.weather" 3 1 "--config retention.ms=2592000000 --config compression.type=lz4"
create_topic "sensor.flow-meter" 6 1 "--config retention.ms=2592000000 --config compression.type=lz4"

# Control command topics
create_topic "control.gate-commands" 3 1 "--config retention.ms=604800000 --config min.insync.replicas=1"
create_topic "control.pump-commands" 3 1 "--config retention.ms=604800000 --config min.insync.replicas=1"
create_topic "control.valve-commands" 3 1 "--config retention.ms=604800000 --config min.insync.replicas=1"

# System event topics
create_topic "system.alerts" 3 1 "--config retention.ms=2592000000"
create_topic "system.notifications" 3 1 "--config retention.ms=604800000"
create_topic "system.audit-log" 1 1 "--config retention.ms=31536000000 --config compression.type=gzip"

# Analytics topics
create_topic "analytics.water-usage" 3 1 "--config retention.ms=31536000000 --config compression.type=gzip"
create_topic "analytics.irrigation-efficiency" 3 1 "--config retention.ms=31536000000 --config compression.type=gzip"

# Integration topics
create_topic "integration.scada-events" 6 1 "--config retention.ms=604800000"
create_topic "integration.weather-updates" 1 1 "--config retention.ms=604800000"
create_topic "integration.crop-data" 3 1 "--config retention.ms=2592000000"

# Dead letter queue topics
create_topic "dlq.sensor-data" 1 1 "--config retention.ms=604800000"
create_topic "dlq.control-commands" 1 1 "--config retention.ms=604800000"

echo "All topics created successfully!"

# List all topics
echo -e "\nListing all topics:"
docker exec $KAFKA_CONTAINER kafka-topics --list --bootstrap-server $KAFKA_BOOTSTRAP_SERVER