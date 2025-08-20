import { Logger } from 'pino';
import { TimescaleRepository } from '../repository/timescale.repository';
import { DualWriteRepository } from '../repository/dual-write.repository';
import { SensorType } from '../models/sensor.model';
import { extractWaterLevelSensorId } from '../utils/sensor-id-formatter';
// import { parseTimestamp } from './sqs-processor-helpers';
import { processMoistureDataEnhanced } from './sqs-processor-moisture-fix';

// Calculate data quality score
function calculateQualityScore(data: any, sensorType: string): number {
  let score = 1.0;
  
  // Check for missing or invalid values
  switch (sensorType) {
    case 'water-level':
      if (data.level === undefined || data.level < 0 || data.level > 30) score -= 0.3;
      if (data.voltage < 300 || data.voltage > 500) score -= 0.2; // Assuming 3.0-5.0V range
      if (data.RSSI < -100) score -= 0.1;
      break;
      
    case 'moisture':
      if (data.humid_hi === undefined || data.humid_hi < 0 || data.humid_hi > 100) score -= 0.2;
      if (data.humid_low === undefined || data.humid_low < 0 || data.humid_low > 100) score -= 0.2;
      if (data.sensor_batt && parseInt(data.sensor_batt) < 360) score -= 0.2; // Low battery
      break;
  }
  
  return Math.max(0, score);
}

// Process water level sensor data
async function processWaterLevelData(
  repo: TimescaleRepository | DualWriteRepository,
  telemetryData: any,
  logger: Logger
): Promise<void> {
  const { data, location, metadata, timestamp } = telemetryData;
  
  // Format sensor ID as AWD-XXXX from MAC address or numeric ID
  let formattedSensorId: string;
  try {
    formattedSensorId = extractWaterLevelSensorId(telemetryData);
    logger.debug({ 
      originalId: telemetryData.sensorId, 
      formattedId: formattedSensorId,
      macAddress: data.macAddress 
    }, 'Formatted water level sensor ID');
  } catch (error) {
    logger.error({ error, telemetryData }, 'Failed to format sensor ID, using original');
    formattedSensorId = telemetryData.sensorId;
  }
  
  const qualityScore = calculateQualityScore(data, 'water-level');
  
  // First, ensure sensor is registered
  try {
    await repo.updateSensorRegistry({
      sensorId: formattedSensorId,
      sensorType: SensorType.WATER_LEVEL,
      manufacturer: 'RID-R',
      currentLocation: location,
      lastSeen: new Date(),
      metadata: metadata || {}
    });
    
    logger.debug({ sensorId: formattedSensorId }, 'Sensor registered/updated');
  } catch (error) {
    logger.error({ error, sensorId: formattedSensorId }, 'Failed to register sensor');
    throw error;
  }
  
  // Save generic sensor reading
  try {
    await repo.saveSensorReading({
      sensorId: formattedSensorId,
      sensorType: SensorType.WATER_LEVEL,
      timestamp: new Date(timestamp),
      location,
      data: { level: parseFloat(data.level), unit: 'cm', ...data },
      metadata: { ...metadata },
      qualityScore
    });
  } catch (error) {
    logger.error({ error, sensorId: formattedSensorId }, 'Failed to save sensor reading');
    throw error;
  }
  
  // Save specific water level reading
  try {
    logger.info({ sensorId: formattedSensorId, level: data.level }, 'Attempting to save water level reading');
    
    // Handle timestamp - check if it's in seconds or milliseconds
    let readingTimestamp: Date;
    if (data.timestamp) {
      try {
        // Convert to number if it's a string
        const timestampNum = typeof data.timestamp === 'string' ? parseInt(data.timestamp, 10) : data.timestamp;
        
        // Validate the timestamp is reasonable (between year 2000 and 2100)
        const minTimestamp = 946684800000; // Jan 1, 2000
        const maxTimestamp = 4102444800000; // Jan 1, 2100
        
        if (isNaN(timestampNum) || timestampNum < minTimestamp || timestampNum > maxTimestamp) {
          logger.warn({ 
            originalTimestamp: data.timestamp, 
            parsed: timestampNum 
          }, 'Invalid timestamp detected, using telemetry timestamp');
          readingTimestamp = new Date(timestamp);
        } else {
          // If timestamp is less than 10 billion, it's likely in seconds
          const ts = timestampNum < 10000000000 ? timestampNum * 1000 : timestampNum;
          readingTimestamp = new Date(ts);
        }
      } catch (err) {
        logger.warn({ 
          error: err, 
          timestamp: data.timestamp 
        }, 'Failed to parse data timestamp, using telemetry timestamp');
        readingTimestamp = new Date(timestamp);
      }
    } else {
      readingTimestamp = new Date(timestamp);
    }
    
    await repo.saveWaterLevelReading({
      sensorId: formattedSensorId,
      timestamp: readingTimestamp,
      location,
      levelCm: data.level,
      voltage: data.voltage / 100, // Convert to actual voltage
      rssi: data.RSSI,
      qualityScore
    });
    
    logger.info({
      sensorId: formattedSensorId,
      level: data.level,
      qualityScore
    }, 'Successfully saved water level reading to water_level_readings table');
  } catch (error) {
    logger.error({ error, sensorId: formattedSensorId }, 'Failed to save water level reading');
    throw error;
  }
  
  // Add location history if location is provided
  if (location) {
    try {
      await repo.addLocationHistory({
        sensorId: formattedSensorId,
        timestamp: new Date(timestamp),
        location,
        reason: 'Regular update'
      });
    } catch (error) {
      logger.warn({ error, sensorId: formattedSensorId }, 'Failed to add location history');
      // Don't throw - this is not critical
    }
  }
}

// Process moisture sensor data - DEPRECATED: Use processMoistureDataEnhanced instead
/*
async function processMoistureData(
  repo: TimescaleRepository,
  telemetryData: any,
  logger: Logger
): Promise<void> {
  const { data, location, metadata, timestamp } = telemetryData;
  
  // Gateway data - use gateway ID if no sensor data is available
  const gatewayId = data.gw_id || telemetryData.sensorId;
  
  // First, process gateway data (always available)
  const gatewayLocation = {
    lat: parseFloat(data.latitude) || location?.lat || 0,
    lng: parseFloat(data.longitude) || location?.lng || 0
  };
  
  // Register gateway as a sensor
  try {
    await repo.updateSensorRegistry({
      sensorId: gatewayId,
      sensorType: SensorType.MOISTURE,
      manufacturer: 'M2M',
      model: 'Gateway',
      currentLocation: gatewayLocation,
      lastSeen: new Date(),
      metadata: {
        ...metadata,
        isGateway: true,
        msgType: data.msg_type
      }
    });
    logger.debug({ gatewayId }, 'Gateway registered/updated');
  } catch (error) {
    logger.error({ error, gatewayId }, 'Failed to register gateway');
    throw error;
  }
  
  // Save gateway environmental data
  try {
    const gatewayTimestamp = parseTimestamp(data.date, data.time, timestamp, logger);
    
    await repo.saveSensorReading({
      sensorId: gatewayId,
      sensorType: SensorType.MOISTURE,
      timestamp: gatewayTimestamp,
      location: gatewayLocation,
      data: {
        temperature: parseFloat(data.temperature),
        humidity: parseFloat(data.humidity),
        headIndex: parseFloat(data.head_index),
        battery: parseFloat(data.batt),
        msgType: data.msg_type,
        sensorCount: data.sensor?.length || 0
      },
      metadata: { 
        ...metadata,
        isGateway: true 
      },
      qualityScore: 0.9 // Gateway data is usually reliable
    });
    
    logger.debug({ gatewayId }, 'Gateway reading saved');
  } catch (error) {
    logger.error({ error, gatewayId }, 'Failed to save gateway reading');
    // Continue processing sensors even if gateway save fails
  }
  
  // Now process sensor array if available
  if (data.sensor && Array.isArray(data.sensor)) {
    for (const sensorData of data.sensor) {
      // Skip empty sensor data (case 2)
      if (!sensorData.sensor_id || sensorData.sensor_id === '') {
        logger.debug({ gatewayId }, 'Skipping empty sensor data');
        continue;
      }
      
      try {
        await processSingleMoistureSensor(
          repo, 
          gatewayId, 
          sensorData, 
          gatewayLocation, 
          metadata, 
          timestamp, 
          logger
        );
      } catch (error) {
        logger.error({ 
          error, 
          sensorId: sensorData.sensor_id,
          gatewayId 
        }, 'Failed to process individual sensor');
        // Continue with other sensors
      }
    }
  }
}
*/

// Main processing function - NO TRANSACTION to avoid foreign key issues
export async function processIncomingData(
  repo: TimescaleRepository | DualWriteRepository,
  telemetryData: any,
  logger: Logger
): Promise<void> {
  try {
    logger.debug({
      sensorType: telemetryData.sensorType,
      sensorId: telemetryData.sensorId
    }, 'Processing sensor data');
    
    switch (telemetryData.sensorType) {
      case 'water-level':
        await processWaterLevelData(repo, telemetryData, logger);
        break;
        
      case 'moisture':
        await processMoistureDataEnhanced(repo, telemetryData, logger);
        break;
        
      default:
        logger.warn(`Unknown sensor type: ${telemetryData.sensorType}`);
        // Still store in generic table
        await repo.saveSensorReading({
          sensorId: telemetryData.sensorId,
          sensorType: telemetryData.sensorType || 'unknown',
          timestamp: new Date(telemetryData.timestamp),
          location: telemetryData.location,
          data: telemetryData.data,
          metadata: telemetryData.metadata,
          qualityScore: 0.5
        });
    }
    
    logger.info({
      sensorType: telemetryData.sensorType,
      sensorId: telemetryData.sensorId
    }, 'Successfully processed sensor data');
    
  } catch (error) {
    logger.error({
      error,
      sensorType: telemetryData.sensorType,
      sensorId: telemetryData.sensorId
    }, 'Failed to process sensor data');
    throw error;
  }
}