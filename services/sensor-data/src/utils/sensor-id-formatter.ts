/**
 * Format water level sensor ID as AWD-XXXX where XXXX is last 4 characters of MAC address
 */
export function formatWaterLevelSensorId(macAddress: string): string {
  if (!macAddress || macAddress.length < 4) {
    throw new Error('Invalid MAC address for sensor ID formatting');
  }
  
  // Get last 4 characters of MAC address
  const last4 = macAddress.slice(-4).toUpperCase();
  
  return `AWD-${last4}`;
}

/**
 * Extract and format sensor ID from water level telemetry data
 */
export function extractWaterLevelSensorId(data: any): string {
  // Try to get MAC address from various possible locations
  const macAddress = data.macAddress || data.mac_address || data.MAC || data.mac;
  
  if (!macAddress) {
    throw new Error('No MAC address found in water level sensor data');
  }
  
  return formatWaterLevelSensorId(macAddress);
}