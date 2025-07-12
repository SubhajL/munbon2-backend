import json
import asyncio
from typing import Dict, Any, List
import structlog
from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaError

from config import settings
from core.metrics import sensor_readings_total, sensor_errors_total
from db import DatabaseManager

logger = structlog.get_logger()


class KafkaConsumerService:
    """Kafka consumer for sensor data streams"""
    
    def __init__(self):
        self.consumer: AIOKafkaConsumer = None
        self.db_manager = DatabaseManager()
        self.batch_processor = BatchProcessor()
        self.running = False
    
    async def start(self) -> None:
        """Start consuming messages from Kafka"""
        try:
            self.consumer = AIOKafkaConsumer(
                settings.kafka_topic_sensors,
                bootstrap_servers=settings.kafka_brokers_list,
                group_id=settings.kafka_consumer_group,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                enable_auto_commit=False,
                auto_offset_reset='latest'
            )
            
            await self.consumer.start()
            self.running = True
            logger.info("Kafka consumer started", topic=settings.kafka_topic_sensors)
            
            # Start consuming messages
            await self._consume_messages()
            
        except Exception as e:
            logger.error("Failed to start Kafka consumer", error=str(e))
            raise
    
    async def stop(self) -> None:
        """Stop the Kafka consumer"""
        self.running = False
        if self.consumer:
            await self.consumer.stop()
            logger.info("Kafka consumer stopped")
    
    async def _consume_messages(self) -> None:
        """Main message consumption loop"""
        batch = []
        last_batch_time = asyncio.get_event_loop().time()
        
        try:
            async for msg in self.consumer:
                if not self.running:
                    break
                
                try:
                    # Process message
                    sensor_data = await self._process_message(msg.value)
                    if sensor_data:
                        batch.append(sensor_data)
                        sensor_readings_total.labels(
                            sensor_type=sensor_data.get("sensor_type", "unknown"),
                            location_id=sensor_data.get("location_id", "unknown")
                        ).inc()
                    
                    # Check if batch should be processed
                    current_time = asyncio.get_event_loop().time()
                    time_since_last_batch = (current_time - last_batch_time) * 1000  # Convert to ms
                    
                    if len(batch) >= settings.max_batch_size or time_since_last_batch >= settings.batch_timeout_ms:
                        if batch:
                            await self.batch_processor.process_batch(batch, self.db_manager)
                            batch = []
                            last_batch_time = current_time
                        
                        # Commit offsets after successful processing
                        await self.consumer.commit()
                    
                except Exception as e:
                    logger.error("Error processing message", error=str(e))
                    sensor_errors_total.labels(
                        sensor_type="unknown",
                        error_type="processing_error"
                    ).inc()
                    
        except KafkaError as e:
            logger.error("Kafka consumer error", error=str(e))
        finally:
            # Process any remaining messages in batch
            if batch:
                await self.batch_processor.process_batch(batch, self.db_manager)
                await self.consumer.commit()
    
    async def _process_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Process and validate individual message"""
        try:
            # Extract sensor data
            sensor_data = {
                "sensor_id": message.get("sensor_id"),
                "sensor_type": message.get("sensor_type"),
                "location_id": message.get("location_id"),
                "channel_id": message.get("channel_id", "main"),
                "timestamp": message.get("timestamp"),
                "flow_rate": float(message.get("flow_rate", 0)),
                "velocity": float(message.get("velocity", 0)),
                "water_level": float(message.get("water_level", 0)),
                "pressure": float(message.get("pressure", 0)),
                "quality_flag": int(message.get("quality_flag", 1))
            }
            
            # Validate required fields
            if not all([sensor_data["sensor_id"], sensor_data["location_id"], sensor_data["timestamp"]]):
                raise ValueError("Missing required fields")
            
            return sensor_data
            
        except Exception as e:
            logger.error("Invalid sensor data", error=str(e), message=message)
            sensor_errors_total.labels(
                sensor_type=message.get("sensor_type", "unknown"),
                error_type="validation_error"
            ).inc()
            return None


class BatchProcessor:
    """Process batches of sensor data"""
    
    async def process_batch(self, batch: List[Dict[str, Any]], db_manager: DatabaseManager) -> None:
        """Process a batch of sensor readings"""
        try:
            # Write to InfluxDB for real-time data
            await db_manager.influxdb.write_flow_data(batch)
            
            # Update Redis cache with latest values
            await self._update_cache(batch, db_manager)
            
            # Check for anomalies
            await self._check_anomalies(batch, db_manager)
            
            logger.info("Processed sensor data batch", batch_size=len(batch))
            
        except Exception as e:
            logger.error("Failed to process batch", error=str(e))
            raise
    
    async def _update_cache(self, batch: List[Dict[str, Any]], db_manager: DatabaseManager) -> None:
        """Update Redis cache with latest readings"""
        # Group by location
        latest_by_location = {}
        for reading in batch:
            location_id = reading["location_id"]
            if location_id not in latest_by_location or reading["timestamp"] > latest_by_location[location_id]["timestamp"]:
                latest_by_location[location_id] = reading
        
        # Update cache
        for location_id, data in latest_by_location.items():
            await db_manager.redis.set_latest_flow_data(location_id, data)
            
            # Publish update for real-time subscribers
            await db_manager.redis.publish_flow_update(f"flow:updates:{location_id}", data)
    
    async def _check_anomalies(self, batch: List[Dict[str, Any]], db_manager: DatabaseManager) -> None:
        """Basic anomaly detection on batch data"""
        # This is a placeholder for anomaly detection logic
        # In production, this would use more sophisticated algorithms
        for reading in batch:
            # Check for zero flow when water level is high
            if reading["water_level"] > 2.0 and reading["flow_rate"] < 0.1:
                anomaly = {
                    "location_id": reading["location_id"],
                    "anomaly_type": "zero_flow_high_level",
                    "severity": "warning",
                    "detected_value": reading["flow_rate"],
                    "expected_value": reading["water_level"] * 0.5,  # Simple estimation
                    "timestamp": reading["timestamp"]
                }
                await db_manager.redis.set_anomaly_flag(
                    reading["location_id"],
                    "zero_flow_high_level",
                    anomaly
                )