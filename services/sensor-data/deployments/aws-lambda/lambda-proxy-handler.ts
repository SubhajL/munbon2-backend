import { APIGatewayProxyHandler } from 'aws-lambda';

const INTERNAL_API_URL = process.env.INTERNAL_API_URL || 'https://munbon-api.YOUR_DOMAIN.com';
const INTERNAL_API_KEY = process.env.INTERNAL_API_KEY || 'your-internal-key';

// Helper to proxy requests to internal API
const proxyToInternal = async (path: string, queryParams?: any) => {
  const url = new URL(`${INTERNAL_API_URL}/api/v1${path}`);
  
  if (queryParams) {
    Object.keys(queryParams).forEach(key => 
      url.searchParams.append(key, queryParams[key])
    );
  }

  const response = await fetch(url.toString(), {
    headers: {
      'X-Internal-Key': INTERNAL_API_KEY,
      'X-Forwarded-For': 'AWS Lambda'
    }
  });

  if (!response.ok) {
    throw new Error(`Internal API error: ${response.status}`);
  }

  return response.json();
};

// Water level latest endpoint
export const waterLevelLatest: APIGatewayProxyHandler = async (event) => {
  try {
    // Validate external API key
    const apiKey = event.headers['X-API-Key'] || event.headers['x-api-key'];
    const validKeys = (process.env.EXTERNAL_API_KEYS || '').split(',');
    
    if (!apiKey || !validKeys.includes(apiKey)) {
      return {
        statusCode: 401,
        body: JSON.stringify({ error: 'Invalid API key' })
      };
    }

    // Proxy to internal API
    const data = await proxyToInternal('/sensors/water-level/latest');
    
    return {
      statusCode: 200,
      headers: {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*'
      },
      body: JSON.stringify(data)
    };
  } catch (error) {
    console.error('Error:', error);
    return {
      statusCode: 500,
      body: JSON.stringify({ error: 'Internal server error' })
    };
  }
};

// Similar handlers for other endpoints...
