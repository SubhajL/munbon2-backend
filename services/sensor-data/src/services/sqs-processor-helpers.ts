import { Logger } from 'pino';
import { TimescaleRepository } from '../repository/timescale.repository';
import { DualWriteRepository } from '../repository/dual-write.repository';
import { SensorType } from '../models/sensor.model';

// Helper function to parse timestamp from date/time strings
export function parseTimestamp(date: string, time: string, fallback: string, logger: Logger): Date {
  try {
    if (date && time && date !== '0000/00/00' && time !== '00:00:00') {
      // Convert date format from YYYY/MM/DD to YYYY-MM-DD for better parsing
      const dateStr = date.replace(/\//g, '-');
      
      // Parse as UTC time
      const utcDate = new Date(`${dateStr}T${time}Z`); // Add 'Z' to indicate UTC
      
      if (!isNaN(utcDate.getTime())) {
        logger.debug({ 
          dateStr, 
          time, 
          utcDate: utcDate.toISOString()
        }, 'Parsed timestamp as UTC');
        
        return utcDate;
      }
    }
  } catch (err) {
    logger.warn({ err, date, time }, 'Failed to parse timestamp, using fallback');
  }
  
  return new Date(fallback);
}

// Helper function to format gateway ID with leading zeros
function formatGatewayId(gwId: string): string {
  // Pad with leading zeros to make it 4 digits
  return gwId.padStart(4, '0');
}

// Process individual moisture sensor data
export async function processSingleMoistureSensor(
  repo: TimescaleRepository | DualWriteRepository,
  gatewayId: string,
  sensorData: any,
  gatewayLocation: { lat: number; lng: number },
  metadata: any,
  timestamp: string,
  logger: Logger
): Promise<void> {
  // Format gateway ID with leading zeros
  const formattedGatewayId = formatGatewayId(gatewayId);
  const sensorId = `${formattedGatewayId}-${sensorData.sensor_id}`;
  
  // Register sensor
  await repo.updateSensorRegistry({
    sensorId,
    sensorType: SensorType.MOISTURE,
    manufacturer: 'M2M',
    model: 'Soil Sensor',
    currentLocation: gatewayLocation,
    lastSeen: new Date(),
    metadata: {
      ...metadata,
      gatewayId: formattedGatewayId,
      originalGatewayId: gatewayId,
      sensorNumber: sensorData.sensor_id
    }
  });
  
  // Parse sensor timestamp
  const sensorTimestamp = parseTimestamp(
    sensorData.sensor_date, 
    sensorData.sensor_utc, 
    timestamp, 
    logger
  );
  
  // Calculate quality score for sensor data
  const qualityScore = calculateMoistureSensorQuality(sensorData);
  
  // Save sensor reading
  await repo.saveSensorReading({
    sensorId,
    sensorType: SensorType.MOISTURE,
    timestamp: sensorTimestamp,
    location: gatewayLocation,
    data: {
      humid_hi: parseFloat(sensorData.humid_hi) || 0,
      humid_low: parseFloat(sensorData.humid_low) || 0,
      temp_hi: parseFloat(sensorData.temp_hi),
      temp_low: parseFloat(sensorData.temp_low),
      amb_humid: parseFloat(sensorData.amb_humid),
      amb_temp: parseFloat(sensorData.amb_temp),
      flood: sensorData.flood,
      sensor_batt: parseFloat(sensorData.sensor_batt),
      sensor_msg_type: sensorData.sensor_msg_type
    },
    metadata: {
      ...metadata,
      gatewayId: formattedGatewayId,
      originalGatewayId: gatewayId,
      sensorNumber: sensorData.sensor_id
    },
    qualityScore
  });
  
  // Save specific moisture reading
  await repo.saveMoistureReading({
    sensorId,
    timestamp: sensorTimestamp,
    location: gatewayLocation,
    moistureSurfacePct: parseFloat(sensorData.humid_hi) || 0,
    moistureDeepPct: parseFloat(sensorData.humid_low) || 0,
    tempSurfaceC: parseFloat(sensorData.temp_hi),
    tempDeepC: parseFloat(sensorData.temp_low),
    ambientHumidityPct: parseFloat(sensorData.amb_humid),
    ambientTempC: parseFloat(sensorData.amb_temp),
    floodStatus: sensorData.flood === 'yes',
    voltage: sensorData.sensor_batt ? parseInt(sensorData.sensor_batt) / 100 : undefined,
    qualityScore
  });
  
  logger.info({ 
    sensorId, 
    surface: sensorData.humid_hi, 
    deep: sensorData.humid_low 
  }, 'Successfully saved moisture sensor reading');
}

// Calculate quality score for moisture sensor data
export function calculateMoistureSensorQuality(sensorData: any): number {
  let score = 1.0;
  
  // Check for missing or invalid humidity values
  const humidHi = parseFloat(sensorData.humid_hi);
  const humidLow = parseFloat(sensorData.humid_low);
  
  if (isNaN(humidHi) || humidHi === 0) score -= 0.3;
  if (isNaN(humidLow) || humidLow === 0) score -= 0.3;
  
  // Check temperature
  const tempHi = parseFloat(sensorData.temp_hi);
  if (isNaN(tempHi) || tempHi < -10 || tempHi > 60) score -= 0.2;
  
  // Check battery
  const battery = parseFloat(sensorData.sensor_batt);
  if (isNaN(battery) || battery < 200) score -= 0.1;
  
  // Check flood status
  if (!sensorData.flood || sensorData.flood === '') score -= 0.1;
  
  return Math.max(0, Math.min(1, score));
}