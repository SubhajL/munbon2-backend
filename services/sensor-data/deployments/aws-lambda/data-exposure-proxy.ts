import { APIGatewayProxyEvent, APIGatewayProxyResult } from 'aws-lambda';
import axios from 'axios';

// Configuration
const TUNNEL_URL = process.env.TUNNEL_URL || 'https://f3b89263-1265-4843-b08c-5391e73e8c75.cfargotunnel.com';
const INTERNAL_API_KEY = process.env.INTERNAL_API_KEY || 'munbon-internal-f3b89263126548';
const EXTERNAL_API_KEYS = (process.env.EXTERNAL_API_KEYS || '').split(',').filter(k => k);

// API Key validation
const validateApiKey = (apiKey: string | undefined): boolean => {
  if (!apiKey) return false;
  return EXTERNAL_API_KEYS.includes(apiKey);
};

// CORS headers
const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'Content-Type,X-API-Key',
  'Access-Control-Allow-Methods': 'GET,OPTIONS',
};

// Response helper
const createResponse = (statusCode: number, body: any): APIGatewayProxyResult => ({
  statusCode,
  headers: {
    'Content-Type': 'application/json',
    ...corsHeaders,
  },
  body: JSON.stringify(body),
});

// Generic proxy handler
const proxyRequest = async (
  event: APIGatewayProxyEvent,
  path: string
): Promise<APIGatewayProxyResult> => {
  try {
    // Validate API Key
    const apiKey = event.headers['X-API-Key'] || event.headers['x-api-key'];
    if (!validateApiKey(apiKey)) {
      return createResponse(401, { error: 'Invalid API key' });
    }

    // Build URL with query parameters
    const queryParams = event.queryStringParameters || {};
    const queryString = Object.entries(queryParams)
      .map(([key, value]) => `${key}=${encodeURIComponent(value || '')}`)
      .join('&');
    
    const url = `${TUNNEL_URL}${path}${queryString ? '?' + queryString : ''}`;

    // Make request to local API via tunnel
    const response = await axios.get(url, {
      headers: {
        'X-Internal-Key': INTERNAL_API_KEY,
      },
      timeout: 25000, // 25 seconds (Lambda timeout is 30)
    });

    return createResponse(200, response.data);
  } catch (error) {
    console.error('Proxy request error:', error);
    
    if (axios.isAxiosError(error)) {
      if (error.response) {
        // The request was made and the server responded with a status code
        // that falls out of the range of 2xx
        return createResponse(error.response.status, error.response.data);
      } else if (error.request) {
        // The request was made but no response was received
        return createResponse(503, { 
          error: 'Service temporarily unavailable',
          message: 'Could not connect to data service'
        });
      }
    }
    
    return createResponse(500, { 
      error: 'Internal server error',
      message: error instanceof Error ? error.message : 'Unknown error'
    });
  }
};

// Water Level Latest Handler
export const waterLevelLatest = async (event: APIGatewayProxyEvent): Promise<APIGatewayProxyResult> => {
  return proxyRequest(event, '/api/v1/sensors/water-level/latest');
};

// Water Level Time Series Handler
export const waterLevelTimeseries = async (event: APIGatewayProxyEvent): Promise<APIGatewayProxyResult> => {
  return proxyRequest(event, '/api/v1/sensors/water-level/timeseries');
};

// Water Level Statistics Handler
export const waterLevelStatistics = async (event: APIGatewayProxyEvent): Promise<APIGatewayProxyResult> => {
  return proxyRequest(event, '/api/v1/sensors/water-level/statistics');
};

// Moisture Latest Handler
export const moistureLatest = async (event: APIGatewayProxyEvent): Promise<APIGatewayProxyResult> => {
  return proxyRequest(event, '/api/v1/sensors/moisture/latest');
};

// Moisture Time Series Handler
export const moistureTimeseries = async (event: APIGatewayProxyEvent): Promise<APIGatewayProxyResult> => {
  return proxyRequest(event, '/api/v1/sensors/moisture/timeseries');
};

// Moisture Statistics Handler
export const moistureStatistics = async (event: APIGatewayProxyEvent): Promise<APIGatewayProxyResult> => {
  return proxyRequest(event, '/api/v1/sensors/moisture/statistics');
};

// AOS Latest Handler
export const aosLatest = async (event: APIGatewayProxyEvent): Promise<APIGatewayProxyResult> => {
  return proxyRequest(event, '/api/v1/sensors/aos/latest');
};

// AOS Time Series Handler
export const aosTimeseries = async (event: APIGatewayProxyEvent): Promise<APIGatewayProxyResult> => {
  return proxyRequest(event, '/api/v1/sensors/aos/timeseries');
};

// AOS Statistics Handler
export const aosStatistics = async (event: APIGatewayProxyEvent): Promise<APIGatewayProxyResult> => {
  return proxyRequest(event, '/api/v1/sensors/aos/statistics');
};

// CORS Options Handler
export const corsOptions = async (event: APIGatewayProxyEvent): Promise<APIGatewayProxyResult> => {
  return createResponse(200, { message: 'OK' });
};