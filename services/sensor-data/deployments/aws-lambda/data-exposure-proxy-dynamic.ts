import { APIGatewayProxyEvent, APIGatewayProxyResult } from 'aws-lambda';
import axios from 'axios';
import { SSMClient, GetParameterCommand } from "@aws-sdk/client-ssm";

// Configuration
const INTERNAL_API_KEY = process.env.INTERNAL_API_KEY || 'munbon-internal-f3b89263126548';

// SSM client for Parameter Store
const ssm = new SSMClient({ region: 'ap-southeast-1' });

// Cache for tunnel URL
let cachedTunnelUrl: string | null = null;
let tunnelCacheExpiry = 0;

// Cache API keys for 5 minutes to reduce Parameter Store calls (FREE tier: 10,000/month)
let cachedApiKeys: string[] = [];
let cacheExpiry = 0;

// Get tunnel URL from Parameter Store with caching
const getTunnelUrl = async (): Promise<string> => {
  // Use cache if still valid (5 minutes)
  if (Date.now() < tunnelCacheExpiry && cachedTunnelUrl) {
    return cachedTunnelUrl;
  }

  try {
    const command = new GetParameterCommand({
      Name: '/munbon/tunnel-url',
      WithDecryption: false
    });
    
    const response = await ssm.send(command);
    const url = response.Parameter?.Value;
    
    if (!url) {
      throw new Error('Tunnel URL not found in Parameter Store');
    }
    
    // Cache for 5 minutes
    cachedTunnelUrl = url;
    tunnelCacheExpiry = Date.now() + (5 * 60 * 1000);
    
    return url;
  } catch (error) {
    console.error('Error fetching tunnel URL from Parameter Store:', error);
    // Fallback to environment variable
    return process.env.TUNNEL_URL || 'https://median-leslie-cartoons-formats.trycloudflare.com';
  }
};

// Get valid API keys from Parameter Store (FREE!)
const getValidApiKeys = async (): Promise<string[]> => {
  // Use cache if still valid
  if (Date.now() < cacheExpiry && cachedApiKeys.length > 0) {
    return cachedApiKeys;
  }

  try {
    const command = new GetParameterCommand({
      Name: '/munbon/api-keys',
      WithDecryption: false  // Not needed for StringList
    });
    
    const response = await ssm.send(command);
    const keys = response.Parameter?.Value?.split(',').map(k => k.trim()) || [];
    
    // Cache for 5 minutes
    cachedApiKeys = keys;
    cacheExpiry = Date.now() + (5 * 60 * 1000);
    
    console.log(`Loaded ${keys.length} API keys from Parameter Store`);
    return keys;
  } catch (error) {
    console.error('Failed to load API keys from Parameter Store:', error);
    // Fallback to environment variable if Parameter Store fails
    const envKeys = process.env.EXTERNAL_API_KEYS || '';
    return envKeys.split(',').map(k => k.trim()).filter(k => k);
  }
};

// Validate API key
const validateApiKey = async (apiKey: string | undefined): Promise<boolean> => {
  if (!apiKey) return false;
  
  const validKeys = await getValidApiKeys();
  return validKeys.includes(apiKey);
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

// Generic proxy function
const proxyRequest = async (event: APIGatewayProxyEvent, path: string): Promise<APIGatewayProxyResult> => {
  try {
    // Check API key
    const apiKey = event.headers['X-API-Key'] || event.headers['x-api-key'];
    
    if (!await validateApiKey(apiKey)) {
      return createResponse(401, { error: 'Invalid API key' });
    }

    // Build URL with query parameters
    const queryParams = event.queryStringParameters || {};
    const queryString = Object.entries(queryParams)
      .map(([key, value]) => `${key}=${encodeURIComponent(value || '')}`)
      .join('&');
    
    // Get tunnel URL from Parameter Store
    const tunnelUrl = await getTunnelUrl();
    const url = `${tunnelUrl}${path}${queryString ? '?' + queryString : ''}`;

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
        return createResponse(error.response.status, error.response.data);
      } else if (error.request) {
        return createResponse(504, { 
          error: 'Gateway timeout - could not reach the backend service',
          details: 'The request to the internal API timed out'
        });
      }
    }
    
    return createResponse(500, { 
      error: 'Internal server error',
      message: error instanceof Error ? error.message : 'Unknown error'
    });
  }
};

// Water Level endpoints
export const waterLevelLatest = async (event: APIGatewayProxyEvent): Promise<APIGatewayProxyResult> => {
  return proxyRequest(event, '/api/v1/sensors/water-level/latest');
};

export const waterLevelTimeseries = async (event: APIGatewayProxyEvent): Promise<APIGatewayProxyResult> => {
  return proxyRequest(event, '/api/v1/sensors/water-level/timeseries');
};

export const waterLevelStatistics = async (event: APIGatewayProxyEvent): Promise<APIGatewayProxyResult> => {
  return proxyRequest(event, '/api/v1/sensors/water-level/statistics');
};

// Moisture endpoints
export const moistureLatest = async (event: APIGatewayProxyEvent): Promise<APIGatewayProxyResult> => {
  return proxyRequest(event, '/api/v1/sensors/moisture/latest');
};

export const moistureTimeseries = async (event: APIGatewayProxyEvent): Promise<APIGatewayProxyResult> => {
  return proxyRequest(event, '/api/v1/sensors/moisture/timeseries');
};

export const moistureStatistics = async (event: APIGatewayProxyEvent): Promise<APIGatewayProxyResult> => {
  return proxyRequest(event, '/api/v1/sensors/moisture/statistics');
};

// AOS Weather endpoints
export const aosLatest = async (event: APIGatewayProxyEvent): Promise<APIGatewayProxyResult> => {
  return proxyRequest(event, '/api/v1/sensors/aos/latest');
};

export const aosTimeseries = async (event: APIGatewayProxyEvent): Promise<APIGatewayProxyResult> => {
  return proxyRequest(event, '/api/v1/sensors/aos/timeseries');
};

export const aosStatistics = async (event: APIGatewayProxyEvent): Promise<APIGatewayProxyResult> => {
  return proxyRequest(event, '/api/v1/sensors/aos/statistics');
};

// CORS preflight
export const corsOptions = async (): Promise<APIGatewayProxyResult> => {
  return {
    statusCode: 200,
    headers: corsHeaders,
    body: '',
  };
};