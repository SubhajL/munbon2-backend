// Lambda Proxy Function for External API V2 - Fixed Version
// This function proxies requests from API Gateway to EC2 API
// API key validation removed to test connectivity

const https = require('https');
const http = require('http');

// Configuration
const EC2_API_BASE = 'http://43.208.201.191:8081';
const INTERNAL_API_KEY = process.env.INTERNAL_API_KEY || 'lambda-internal-key-2025';

exports.handler = async (event, context) => {
    console.log('Received event:', JSON.stringify(event, null, 2));
    
    try {
        // Extract API key (but don't validate it - just pass it through)
        const apiKey = event.headers['x-api-key'] || event.headers['X-API-Key'] || '';
        
        console.log('Received API key:', apiKey);
        console.log('Skipping API key validation for testing...');
        
        // Build the target URL
        const targetPath = event.path || event.rawPath || '/';
        const queryString = event.queryStringParameters ? 
            new URLSearchParams(event.queryStringParameters).toString() : '';
        const targetUrl = `${EC2_API_BASE}${targetPath}${queryString ? '?' + queryString : ''}`;
        
        console.log(`Proxying request to: ${targetUrl}`);
        
        // Make the request to EC2 API
        const startTime = Date.now();
        
        try {
            const response = await makeHttpRequest({
                url: targetUrl,
                method: event.httpMethod || 'GET',
                headers: {
                    'x-api-key': apiKey, // Pass through the original API key
                    'Content-Type': 'application/json',
                    'X-Forwarded-For': event.headers['X-Forwarded-For'] || event.requestContext?.identity?.sourceIp,
                    'X-Original-Request-Id': event.requestContext?.requestId
                },
                body: event.body
            });
            
            console.log(`Request completed in ${Date.now() - startTime}ms with status ${response.statusCode}`);
            
            // Return the response
            return {
                statusCode: response.statusCode,
                headers: {
                    'Content-Type': response.headers['content-type'] || 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type,X-API-Key,x-api-key',
                    'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
                    'X-Proxy-Time': `${Date.now() - startTime}ms`
                },
                body: response.body
            };
            
        } catch (proxyError) {
            console.error('Proxy request failed:', proxyError);
            console.log(`Request failed after ${Date.now() - startTime}ms`);
            
            // Return detailed error for debugging
            return {
                statusCode: 502,
                headers: {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'X-Error-Type': 'proxy-error',
                    'X-Proxy-Time': `${Date.now() - startTime}ms`
                },
                body: JSON.stringify({
                    message: 'Failed to reach backend service',
                    error: proxyError.message,
                    details: {
                        targetUrl: targetUrl,
                        errorCode: proxyError.statusCode || 'NETWORK_ERROR',
                        time: `${Date.now() - startTime}ms`
                    }
                })
            };
        }
        
    } catch (error) {
        console.error('Unexpected error in Lambda proxy:', error);
        
        return {
            statusCode: 500,
            headers: {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            body: JSON.stringify({
                message: 'Internal server error',
                error: error.message,
                type: 'handler-error'
            })
        };
    }
};

// Helper function to make HTTP requests with better error handling
function makeHttpRequest(options) {
    return new Promise((resolve, reject) => {
        const url = new URL(options.url);
        const client = url.protocol === 'https:' ? https : http;
        
        const reqOptions = {
            hostname: url.hostname,
            port: url.port || (url.protocol === 'https:' ? 443 : 80),
            path: url.pathname + url.search,
            method: options.method,
            headers: options.headers,
            timeout: 25000 // 25 seconds timeout
        };
        
        console.log('Making request with options:', {
            hostname: reqOptions.hostname,
            port: reqOptions.port,
            path: reqOptions.path,
            method: reqOptions.method
        });
        
        const req = client.request(reqOptions, (res) => {
            let data = '';
            
            res.on('data', (chunk) => {
                data += chunk;
            });
            
            res.on('end', () => {
                console.log('Response received:', {
                    statusCode: res.statusCode,
                    headers: res.headers
                });
                
                resolve({
                    statusCode: res.statusCode,
                    headers: res.headers,
                    body: data
                });
            });
        });
        
        req.on('error', (error) => {
            console.error('Request error:', error);
            reject({
                statusCode: 502,
                message: `Network error: ${error.message}`,
                code: error.code
            });
        });
        
        req.on('timeout', () => {
            console.error('Request timeout after 25 seconds');
            req.destroy();
            reject({
                statusCode: 504,
                message: 'Request timeout - EC2 API did not respond within 25 seconds'
            });
        });
        
        if (options.body) {
            req.write(options.body);
        }
        
        req.end();
    });
}