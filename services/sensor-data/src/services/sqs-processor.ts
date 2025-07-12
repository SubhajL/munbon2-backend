import { Logger } from 'pino';
import { TimescaleRepository } from '../repository/timescale.repository';
import { SensorType } from '../models/sensor.model';

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
  repo: TimescaleRepository,
  telemetryData: any,
  logger: Logger
): Promise<void> {
  const { sensorId, data, location, metadata, timestamp } = telemetryData;
  const qualityScore = calculateQualityScore(data, 'water-level');
  
  // First, ensure sensor is registered
  try {
    await repo.updateSensorRegistry({
      sensorId,
      sensorType: SensorType.WATER_LEVEL,
      manufacturer: 'RID-R',
      currentLocation: location,
      lastSeen: new Date(),
      metadata: metadata || {}
    });
    
    logger.debug({ sensorId }, 'Sensor registered/updated');
  } catch (error) {
    logger.error({ error, sensorId }, 'Failed to register sensor');
    throw error;
  }
  
  // Save generic sensor reading
  try {
    await repo.saveSensorReading({
      sensorId,
      sensorType: SensorType.WATER_LEVEL,
      timestamp: new Date(timestamp),
      location,
      data: { level: parseFloat(data.level), unit: 'cm', ...data },
      metadata: { ...metadata },
      qualityScore
    });
  } catch (error) {
    logger.error({ error, sensorId }, 'Failed to save sensor reading');
    throw error;
  }
  
  // Save specific water level reading
  try {
    logger.info({ sensorId, level: data.level }, 'Attempting to save water level reading');
    
    // Handle timestamp - check if it's in seconds or milliseconds
    let readingTimestamp: Date;
    if (data.timestamp) {
      // If timestamp is less than 10 billion, it's likely in seconds
      const ts = data.timestamp < 10000000000 ? data.timestamp * 1000 : data.timestamp;
      readingTimestamp = new Date(ts);
    } else {
      readingTimestamp = new Date(timestamp);
    }
    
    await repo.saveWaterLevelReading({
      sensorId,
      timestamp: readingTimestamp,
      location,
      levelCm: data.level,
      voltage: data.voltage / 100, // Convert to actual voltage
      rssi: data.RSSI,
      qualityScore
    });
    
    logger.info({
      sensorId,
      level: data.level,
      qualityScore
    }, 'Successfully saved water level reading to water_level_readings table');
  } catch (error) {
    logger.error({ error, sensorId }, 'Failed to save water level reading');
    throw error;
  }
  
  // Add location history if location is provided
  if (location) {
    try {
      await repo.addLocationHistory({
        sensorId,
        timestamp: new Date(timestamp),
        location,
        reason: 'Regular update'
      });
    } catch (error) {
      logger.warn({ error, sensorId }, 'Failed to add location history');
      // Don't throw - this is not critical
    }
  }
}

// Process moisture sensor data
async function processMoistureData(
  repo: TimescaleRepository,
  telemetryData: any,
  logger: Logger
): Promise<void> {
  const { sensorId, data, location, metadata, timestamp } = telemetryData;
  const qualityScore = calculateQualityScore(data, 'moisture');
  
  // First, ensure sensor is registered
  try {
    await repo.updateSensorRegistry({
      sensorId,
      sensorType: SensorType.MOISTURE,
      manufacturer: 'M2M',
      currentLocation: location,
      lastSeen: new Date(),
      metadata: metadata || {}
    });
    
    logger.debug({ sensorId }, 'Sensor registered/updated');
  } catch (error) {
    logger.error({ error, sensorId }, 'Failed to register sensor');
    throw error;
  }
  
  // Save generic sensor reading - store both top and bottom values
  try {
    await repo.saveSensorReading({
      sensorId,
      sensorType: SensorType.MOISTURE,
      timestamp: new Date(timestamp),
      location,
      data: {
        humid_hi: parseFloat(data.humid_hi),
        humid_low: parseFloat(data.humid_low),
        temp_hi: parseFloat(data.temp_hi),
        temp_low: parseFloat(data.temp_low),
        ...data
      },
      metadata: { ...metadata },
      qualityScore
    });
  } catch (error) {
    logger.error({ error, sensorId }, 'Failed to save sensor reading');
    throw error;
  }
  
  // Parse date and time from moisture data if available
  let sensorTime: Date;
  try {
    if (data.date && data.time) {
      // Convert date format from YYYY/MM/DD to YYYY-MM-DD for better parsing
      const dateStr = data.date.replace(/\//g, '-');
      sensorTime = new Date(`${dateStr}T${data.time}`);
      logger.debug({ dateStr, time: data.time, parsed: sensorTime }, 'Parsed moisture timestamp');
    } else {
      sensorTime = new Date(timestamp);
      logger.debug({ timestamp, parsed: sensorTime }, 'Using telemetry timestamp');
    }
  } catch (err) {
    logger.warn({ err, date: data.date, time: data.time }, 'Failed to parse moisture timestamp, using telemetry timestamp');
    sensorTime = new Date(timestamp);
  }
  
  // Save specific moisture reading
  try {
    logger.info({ sensorId, surface: data.humid_hi, deep: data.humid_low }, 'Attempting to save moisture reading');
    await repo.saveMoistureReading({
      sensorId,
      timestamp: sensorTime,
      location,
      moistureSurfacePct: parseFloat(data.humid_hi),
      moistureDeepPct: parseFloat(data.humid_low),
      tempSurfaceC: parseFloat(data.temp_hi),
      tempDeepC: parseFloat(data.temp_low),
      ambientHumidityPct: parseFloat(data.amb_humid),
      ambientTempC: parseFloat(data.amb_temp),
      floodStatus: data.flood === 'yes',
      voltage: data.sensor_batt ? parseInt(data.sensor_batt) / 100 : undefined,
      qualityScore
    });
    
    logger.info({
      sensorId,
      surface: data.humid_hi,
      deep: data.humid_low,
      qualityScore
    }, 'Successfully saved moisture reading to moisture_readings table');
  } catch (error) {
    logger.error({ error, sensorId }, 'Failed to save moisture reading');
    throw error;
  }
  
  // Add location history if location is provided
  if (location) {
    try {
      await repo.addLocationHistory({
        sensorId,
        timestamp: sensorTime,
        location,
        reason: 'Regular update'
      });
    } catch (error) {
      logger.warn({ error, sensorId }, 'Failed to add location history');
      // Don't throw - this is not critical
    }
  }
}

// Main processing function - NO TRANSACTION to avoid foreign key issues
export async function processIncomingData(
  repo: TimescaleRepository,
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
        await processMoistureData(repo, telemetryData, logger);
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