// Lambda Proxy Function for External API V2
// This function proxies requests from API Gateway to EC2 API

const https = require('https');
const http = require('http');

// Configuration
const EC2_API_BASE = 'http://43.208.201.191:8081';
const INTERNAL_API_KEY = process.env.INTERNAL_API_KEY || 'lambda-internal-key-2025';

// API key validation (from Parameter Store)
const VALID_API_KEYS = {
    'rid-ms-prod-key1': 'RID Main System',
    'tmd-weather-key2': 'Thai Meteorological Department',
    'university-key3': 'University Research'
};

exports.handler = async (event, context) => {
    console.log('Received event:', JSON.stringify(event, null, 2));
    
    try {
        // Extract and validate API key
        const apiKey = event.headers['x-api-key'] || event.headers['X-API-Key'];
        
        if (!apiKey || !VALID_API_KEYS[apiKey]) {
            return {
                statusCode: 401,
                headers: {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                body: JSON.stringify({ error: 'Invalid API key' })
            };
        }
        
        // Build the target URL
        const targetPath = event.path || event.rawPath || '/';
        const queryString = event.rawQueryStringParameters ? 
            new URLSearchParams(event.queryStringParameters).toString() : '';
        const targetUrl = `${EC2_API_BASE}${targetPath}${queryString ? '?' + queryString : ''}`;
        
        console.log(`Proxying request to: ${targetUrl}`);
        
        // Make the request to EC2 API
        const response = await makeHttpRequest({
            url: targetUrl,
            method: event.httpMethod || 'GET',
            headers: {
                'x-api-key': INTERNAL_API_KEY,
                'Content-Type': 'application/json',
                'X-Forwarded-For': event.headers['X-Forwarded-For'] || event.requestContext?.identity?.sourceIp,
                'X-Original-API-Key': apiKey
            },
            body: event.body
        });
        
        // Return the response
        return {
            statusCode: response.statusCode,
            headers: {
                'Content-Type': response.headers['content-type'] || 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type,X-API-Key',
                'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
            },
            body: response.body
        };
        
    } catch (error) {
        console.error('Error in Lambda proxy:', error);
        
        return {
            statusCode: error.statusCode || 502,
            headers: {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            body: JSON.stringify({
                message: 'Internal server error',
                error: error.message,
                details: 'Failed to reach the backend service'
            })
        };
    }
};

// Helper function to make HTTP requests
function makeHttpRequest(options) {
    return new Promise((resolve, reject) => {
        const url = new URL(options.url);
        const client = url.protocol === 'https:' ? https : http;
        
        const reqOptions = {
            hostname: url.hostname,
            port: url.port,
            path: url.pathname + url.search,
            method: options.method,
            headers: options.headers,
            timeout: 25000 // 25 seconds timeout
        };
        
        const req = client.request(reqOptions, (res) => {
            let data = '';
            
            res.on('data', (chunk) => {
                data += chunk;
            });
            
            res.on('end', () => {
                resolve({
                    statusCode: res.statusCode,
                    headers: res.headers,
                    body: data
                });
            });
        });
        
        req.on('error', (error) => {
            reject({
                statusCode: 502,
                message: error.message
            });
        });
        
        req.on('timeout', () => {
            req.destroy();
            reject({
                statusCode: 504,
                message: 'Request timeout'
            });
        });
        
        if (options.body) {
            req.write(options.body);
        }
        
        req.end();
    });
}