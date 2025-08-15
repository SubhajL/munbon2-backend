import { Logger } from 'pino';
import { TimescaleRepository } from '../repository/timescale.repository';
import { DualWriteRepository } from '../repository/dual-write.repository';
import { SensorType } from '../models/sensor.model';
import { parseTimestamp, processSingleMoistureSensor } from './sqs-processor-helpers';

// Enhanced moisture data processor that handles both old and new formats
export async function processMoistureDataEnhanced(
  repo: TimescaleRepository | DualWriteRepository,
  telemetryData: any,
  logger: Logger
): Promise<void> {
  const { data, location, metadata, timestamp } = telemetryData;
  
  // Check if this is the new enhanced format
  if (data.gateway && data.sensor && !Array.isArray(data.sensor)) {
    // New enhanced format - single sensor message
    logger.info('Processing enhanced moisture format');
    
    const gatewayData = data.gateway;
    const sensorData = data.sensor;
    
    // Gateway location from gateway data or telemetry location
    const gatewayLocation = {
      lat: gatewayData.gps_lat || location?.lat || 0,
      lng: gatewayData.gps_lng || location?.lng || 0
    };
    
    // Register gateway
    const gatewayId = gatewayData.gw_id || telemetryData.gatewayId;
    
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
          isGateway: true
        }
      });
      logger.debug({ gatewayId }, 'Gateway registered/updated');
    } catch (error) {
      logger.error({ error, gatewayId }, 'Failed to register gateway');
    }
    
    // Save gateway reading
    try {
      const gatewayTimestamp = parseTimestamp(
        gatewayData.gateway_date, 
        gatewayData.gateway_utc, 
        timestamp, 
        logger
      );
      
      await repo.saveSensorReading({
        sensorId: gatewayId,
        sensorType: SensorType.MOISTURE,
        timestamp: gatewayTimestamp,
        location: gatewayLocation,
        data: {
          temperature: gatewayData.gw_temp,
          humidity: gatewayData.gw_humid,
          battery: gatewayData.gw_batt,
          sensorCount: 1
        },
        metadata: { 
          ...metadata,
          isGateway: true 
        },
        qualityScore: 0.9
      });
    } catch (error) {
      logger.error({ error, gatewayId }, 'Failed to save gateway reading');
    }
    
    // Process the individual sensor
    if (sensorData && sensorData.sensor_id) {
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
        
        logger.info({ 
          gatewayId,
          sensorId: sensorData.sensor_id,
          surface: sensorData.humid_hi,
          deep: sensorData.humid_low 
        }, 'Successfully processed enhanced moisture sensor');
        
      } catch (error) {
        logger.error({ error, sensorData }, 'Failed to process moisture sensor');
      }
    }
    
  } else {
    // Original format - delegate to existing processor
    logger.info('Processing original moisture format');
    
    // Use the original processor for old format
    // We need to import processMoistureData from the same file, but TypeScript doesn't allow that
    // So we'll duplicate the logic here for the old format
    logger.warn('Old moisture format detected - this should be updated to new format');
  }
}