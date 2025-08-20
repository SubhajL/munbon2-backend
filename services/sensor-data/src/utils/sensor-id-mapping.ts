// Static mapping for known numeric sensor IDs to AWD format
// Based on sensor registry data
export const SENSOR_ID_MAPPINGS: Record<string, string> = {
  // Numeric ID -> AWD ID
  '222410831183230': 'AWD-B7E6',  // MAC: 16186C1FB7E6
  '2216617412385143': 'AWD-D977', // This needs to be verified
  // Add more mappings as discovered
};

/**
 * Map numeric sensor IDs to their AWD format using known mappings
 */
export function mapNumericSensorId(numericId: string): string | null {
  return SENSOR_ID_MAPPINGS[numericId] || null;
}