import type { VercelRequest, VercelResponse } from '@vercel/node';

// Environment variables (set in Vercel dashboard)
const INTERNAL_API_URL = process.env.INTERNAL_API_URL || 'http://localhost:3000';
const VALID_API_KEYS = (process.env.VALID_API_KEYS || 'test-key-123').split(',');

// Buddhist calendar conversion
const convertToBuddhistDate = (date: Date): string => {
  const year = date.getFullYear() + 543;
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${day}/${month}/${year}`;
};

export default async function handler(
  req: VercelRequest,
  res: VercelResponse
) {
  // Only allow GET requests
  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  // Validate API key
  const apiKey = req.headers['x-api-key'] as string;
  if (!apiKey || !VALID_API_KEYS.includes(apiKey)) {
    return res.status(401).json({ error: 'Invalid API key' });
  }

  try {
    // For demo/testing, return mock data
    // In production, this would call your local API via tunnel
    const mockData = {
      data_type: 'water_level',
      request_time: new Date().toISOString(),
      request_time_buddhist: convertToBuddhistDate(new Date()),
      sensor_count: 3,
      sensors: [
        {
          sensor_id: 'wl001',
          sensor_name: 'Water Level Sensor 1',
          location: { lat: 14.1234, lon: 102.5678 },
          zone: 'Zone 1',
          latest_reading: {
            timestamp: new Date().toISOString(),
            timestamp_buddhist: convertToBuddhistDate(new Date()),
            water_level_m: 12.5,
            flow_rate_m3s: 1.2,
            quality: 100
          }
        },
        {
          sensor_id: 'wl002',
          sensor_name: 'Water Level Sensor 2',
          location: { lat: 14.2234, lon: 102.6678 },
          zone: 'Zone 2',
          latest_reading: {
            timestamp: new Date().toISOString(),
            timestamp_buddhist: convertToBuddhistDate(new Date()),
            water_level_m: 11.8,
            flow_rate_m3s: 1.1,
            quality: 100
          }
        }
      ]
    };

    // Production version would be:
    // const response = await fetch(`${INTERNAL_API_URL}/api/v1/sensors/water-level/latest`, {
    //   headers: { 'X-Internal-Key': process.env.INTERNAL_KEY }
    // });
    // const data = await response.json();

    return res.status(200).json(mockData);
  } catch (error) {
    console.error('Error:', error);
    return res.status(500).json({ error: 'Internal server error' });
  }
}