import { APIGatewayProxyEvent, APIGatewayProxyResult } from 'aws-lambda';
import * as AWS from 'aws-sdk';

const sqs = new AWS.SQS();

interface WaterLevelData {
  deviceID: string;
  macAddress: string;
  latitude: number;
  longitude: number;
  RSSI: number;
  voltage: number;
  level: number;
  timestamp: number;
}

interface MoistureSensorData {
  gateway_id: string;
  msg_type: string;
  date: string;
  time: string;
  latitude: string;
  longitude: string;
  gw_batt: string;
  sensor: Array<{
    sensor_id: string;
    flood: string;
    amb_humid: string;
    amb_temp: string;
    humid_hi: string;
    temp_hi: string;
    humid_low: string;
    temp_low: string;
    sensor_batt: string;
  }>;
}

interface TelemetryData {
  timestamp: string;
  token: string;
  tokenGroup: string;
  sensorType: 'water-level' | 'moisture' | 'unknown';
  sensorId: string;
  location?: {
    lat: number;
    lng: number;
  };
  data: WaterLevelData | MoistureSensorData | any;
  sourceIp: string;
  metadata?: {
    manufacturer?: string;
    firmware?: string;
    battery?: number;
    rssi?: number;
  };
}

function getValidTokens(): Record<string, string> {
  const tokens: Record<string, string> = {};
  if (process.env.VALID_TOKENS) {
    process.env.VALID_TOKENS.split(',').forEach(pair => {
      const [token, name] = pair.split(':');
      if (token && name) {
        tokens[token.trim()] = name.trim();
      }
    });
  }
  return tokens;
}

function detectSensorType(data: any): 'water-level' | 'moisture' | 'unknown' {
  // Water level sensor detection
  if (data.deviceID && data.level !== undefined && data.macAddress) {
    return 'water-level';
  }
  
  // Moisture sensor detection
  if (data.gateway_id && data.sensor && Array.isArray(data.sensor)) {
    return 'moisture';
  }
  
  return 'unknown';
}

function extractLocationAndMetadata(data: any, sensorType: string): {
  location?: { lat: number; lng: number };
  metadata: any;
  sensorId: string;
} {
  let location: { lat: number; lng: number } | undefined;
  let metadata: any = {};
  let sensorId = 'unknown';

  switch (sensorType) {
    case 'water-level':
      const waterData = data as WaterLevelData;
      location = {
        lat: waterData.latitude,
        lng: waterData.longitude
      };
      metadata = {
        manufacturer: 'RID-R',
        battery: waterData.voltage,
        rssi: waterData.RSSI,
        macAddress: waterData.macAddress
      };
      sensorId = waterData.deviceID;
      break;

    case 'moisture':
      const moistureData = data as MoistureSensorData;
      location = {
        lat: parseFloat(moistureData.latitude),
        lng: parseFloat(moistureData.longitude)
      };
      metadata = {
        manufacturer: 'M2M',
        gatewayBattery: parseInt(moistureData.gw_batt) / 100,
        gatewayId: moistureData.gateway_id,
        msgType: moistureData.msg_type
      };
      // For moisture sensors, we'll process each sensor separately
      sensorId = moistureData.gateway_id;
      break;
  }

  return { location, metadata, sensorId };
}

export const telemetry = async (
  event: APIGatewayProxyEvent
): Promise<APIGatewayProxyResult> => {
  try {
    const token = event.pathParameters?.token;
    const body = JSON.parse(event.body || '{}');
    const validTokens = getValidTokens();
    
    if (!token || !validTokens[token]) {
      return {
        statusCode: 401,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ error: 'Invalid token' })
      };
    }
    
    const sensorType = detectSensorType(body);
    const { location, metadata, sensorId } = extractLocationAndMetadata(body, sensorType);
    
    // For moisture sensors with multiple sensor arrays, send each as separate message
    if (sensorType === 'moisture' && body.sensor && Array.isArray(body.sensor)) {
      const moistureData = body as MoistureSensorData;
      const messages = moistureData.sensor.map(sensor => {
        const telemetryData: TelemetryData = {
          timestamp: new Date().toISOString(),
          token: token,
          tokenGroup: validTokens[token],
          sensorType: 'moisture',
          sensorId: `${moistureData.gateway_id}-${sensor.sensor_id}`,
          location,
          data: {
            ...sensor,
            gateway_id: moistureData.gateway_id,
            date: moistureData.date,
            time: moistureData.time,
            msg_type: moistureData.msg_type
          },
          sourceIp: event.requestContext.identity.sourceIp || 'unknown',
          metadata: {
            ...metadata,
            sensorBattery: parseInt(sensor.sensor_batt) / 100
          }
        };
        
        return {
          Id: `${moistureData.gateway_id}-${sensor.sensor_id}-${Date.now()}`,
          MessageBody: JSON.stringify(telemetryData)
        };
      });
      
      // Send batch messages
      if (messages.length > 0) {
        await sqs.sendMessageBatch({
          QueueUrl: process.env.SQS_QUEUE_URL!,
          Entries: messages.slice(0, 10) // SQS batch limit is 10
        }).promise();
        
        // Send remaining messages if more than 10
        if (messages.length > 10) {
          for (let i = 10; i < messages.length; i += 10) {
            await sqs.sendMessageBatch({
              QueueUrl: process.env.SQS_QUEUE_URL!,
              Entries: messages.slice(i, i + 10)
            }).promise();
          }
        }
      }
    } else {
      // Single sensor data (water level or unknown)
      const telemetryData: TelemetryData = {
        timestamp: new Date().toISOString(),
        token: token,
        tokenGroup: validTokens[token],
        sensorType,
        sensorId,
        location,
        data: body,
        sourceIp: event.requestContext.identity.sourceIp || 'unknown',
        metadata
      };
      
      await sqs.sendMessage({
        QueueUrl: process.env.SQS_QUEUE_URL!,
        MessageBody: JSON.stringify(telemetryData)
      }).promise();
    }
    
    console.log(`Received ${sensorType} data from ${sensorId}`);
    
    return {
      statusCode: 200,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        status: 'success',
        message: 'Telemetry received',
        timestamp: new Date().toISOString()
      })
    };
  } catch (error) {
    console.error('Error processing telemetry:', error);
    return {
      statusCode: 500,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ error: 'Internal server error' })
    };
  }
};

// Handle configuration requests for moisture sensors
export const attributes = async (
  event: APIGatewayProxyEvent
): Promise<APIGatewayProxyResult> => {
  try {
    const token = event.pathParameters?.token;
    const sharedKeys = event.queryStringParameters?.sharedKeys;
    const validTokens = getValidTokens();
    
    if (!token || !validTokens[token]) {
      return {
        statusCode: 401,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ error: 'Invalid token' })
      };
    }
    
    // Configuration values for different sensor types
    const configs: Record<string, any> = {
      interval: {
        water_level: 60,      // 1 minute for water level
        moisture: 300,        // 5 minutes for moisture
        default: 300
      },
      thresholds: {
        water_level_critical_high: 25,  // cm
        water_level_critical_low: 5,    // cm
        moisture_critical_low: 20,      // %
        moisture_optimal: 60            // %
      },
      calibration: {
        water_level_offset: 0,
        moisture_offset: 0
      }
    };
    
    const response = sharedKeys ? configs[sharedKeys] || {} : configs;
    
    return {
      statusCode: 200,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(response)
    };
  } catch (error) {
    console.error('Error getting attributes:', error);
    return {
      statusCode: 500,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ error: 'Internal server error' })
    };
  }
};