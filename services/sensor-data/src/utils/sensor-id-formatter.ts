import { mapNumericSensorId } from './sensor-id-mapping';

/**
 * Format water level sensor ID as AWD-XXXX using known mappings or MAC address
 */
export function formatWaterLevelSensorId(sensorIdOrMac: string): string {
  if (!sensorIdOrMac || sensorIdOrMac.length < 4) {
    throw new Error('Invalid sensor ID or MAC address for formatting');
  }
  
  // If already in AWD format, return as is
  if (sensorIdOrMac.startsWith('AWD-')) {
    return sensorIdOrMac;
  }
  
  // Check if it's a numeric sensor ID with known mapping
  if (/^\d+$/.test(sensorIdOrMac)) {
    const mappedId = mapNumericSensorId(sensorIdOrMac);
    if (mappedId) {
      return mappedId;
    }
    // If no mapping found, log warning and use hex conversion as fallback
    console.warn(`No mapping found for numeric sensor ID: ${sensorIdOrMac}, using hex conversion`);
    const hex = BigInt(sensorIdOrMac).toString(16).toUpperCase();
    const last4 = hex.slice(-4).padStart(4, '0');
    return `AWD-${last4}`;
  }
  
  // Otherwise treat as MAC address - remove colons and get last 4 characters
  const cleanMac = sensorIdOrMac.replace(/[:-]/g, '');
  const last4 = cleanMac.slice(-4).toUpperCase();
  
  return `AWD-${last4}`;
}

/**
 * Extract and format sensor ID from water level telemetry data
 */
export function extractWaterLevelSensorId(telemetryData: any): string {
  // PRIORITY: Always use MAC address if available (as per AWD-XXXX standard)
  const data = telemetryData.data || telemetryData;
  const macAddress = data.macAddress || data.mac_address || data.MAC || data.mac;
  
  if (macAddress) {
    // AWD-XXXX format uses last 4 characters of MAC address
    return formatWaterLevelSensorId(macAddress);
  }
  
  // Fallback: Use sensor ID if no MAC address available
  if (telemetryData.sensorId) {
    // Check if it's already in AWD format
    if (telemetryData.sensorId.startsWith('AWD-')) {
      return telemetryData.sensorId;
    }
    // Otherwise format it (for backward compatibility)
    return formatWaterLevelSensorId(telemetryData.sensorId);
  }
  
  throw new Error('No sensor ID or MAC address found in water level sensor data');
}