const express = require('express');
const swaggerUi = require('swagger-ui-express');
const YAML = require('yamljs');
const path = require('path');
const fs = require('fs');

const app = express();

// Load OpenAPI specification
const openapiPath = path.join(__dirname, '../../../api-contracts/openapi/external-api.yaml');
const openapiDocument = YAML.load(openapiPath);

// Custom CSS for branding
const customCss = `
  .swagger-ui .topbar {
    display: none;
  }
  .swagger-ui .info .title {
    color: #2c5282;
  }
  .swagger-ui .btn.authorize {
    background-color: #2b6cb0;
    border-color: #2b6cb0;
  }
  .swagger-ui .btn.authorize:hover {
    background-color: #2c5282;
    border-color: #2c5282;
  }
`;

// Custom site title and favicon
const customSiteTitle = 'Munbon External API Documentation';
const customfavIcon = '/favicon.ico';

// Swagger UI options
const swaggerOptions = {
  customCss,
  customSiteTitle,
  customfavIcon,
  explorer: true,
  swaggerOptions: {
    persistAuthorization: true,
    displayRequestDuration: true,
    tryItOutEnabled: true,
    filter: true,
    validatorUrl: null,
    defaultModelsExpandDepth: 1,
    defaultModelExpandDepth: 1,
    docExpansion: 'list',
    tagsSorter: 'alpha',
    operationsSorter: 'alpha'
  }
};

// API Documentation landing page
app.get('/', (req, res) => {
  res.send(`
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>Munbon External API Documentation</title>
      <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
          line-height: 1.6;
          color: #333;
          background: #f5f5f5;
        }
        .container {
          max-width: 1200px;
          margin: 0 auto;
          padding: 2rem;
        }
        .header {
          background: #2c5282;
          color: white;
          padding: 3rem 0;
          text-align: center;
          margin-bottom: 3rem;
          border-radius: 8px;
        }
        .header h1 {
          font-size: 2.5rem;
          margin-bottom: 1rem;
        }
        .header p {
          font-size: 1.2rem;
          opacity: 0.9;
        }
        .section {
          background: white;
          padding: 2rem;
          margin-bottom: 2rem;
          border-radius: 8px;
          box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .section h2 {
          color: #2c5282;
          margin-bottom: 1rem;
        }
        .section h3 {
          color: #2d3748;
          margin: 1.5rem 0 0.5rem 0;
        }
        .api-key-tiers {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
          gap: 1rem;
          margin-top: 1rem;
        }
        .tier-card {
          border: 1px solid #e2e8f0;
          padding: 1.5rem;
          border-radius: 8px;
          text-align: center;
        }
        .tier-card h4 {
          color: #2c5282;
          margin-bottom: 0.5rem;
        }
        .tier-card .limit {
          font-size: 2rem;
          font-weight: bold;
          color: #38a169;
        }
        .tier-card .period {
          color: #718096;
        }
        .code {
          background: #f7fafc;
          padding: 1rem;
          border-radius: 4px;
          font-family: 'Courier New', monospace;
          overflow-x: auto;
          margin: 1rem 0;
        }
        .btn {
          display: inline-block;
          background: #2b6cb0;
          color: white;
          padding: 0.75rem 2rem;
          text-decoration: none;
          border-radius: 4px;
          margin-top: 1rem;
          transition: background 0.3s;
        }
        .btn:hover {
          background: #2c5282;
        }
        .endpoints-grid {
          display: grid;
          gap: 1rem;
          margin-top: 1rem;
        }
        .endpoint {
          display: flex;
          align-items: center;
          padding: 0.75rem;
          background: #f7fafc;
          border-radius: 4px;
        }
        .method {
          font-weight: bold;
          margin-right: 1rem;
          padding: 0.25rem 0.5rem;
          border-radius: 4px;
          font-size: 0.875rem;
        }
        .method.get { background: #48bb78; color: white; }
        .method.post { background: #4299e1; color: white; }
        .path {
          font-family: 'Courier New', monospace;
          color: #2d3748;
        }
      </style>
    </head>
    <body>
      <div class="container">
        <div class="header">
          <h1>Munbon External API</h1>
          <p>Unified API for Munbon Irrigation Control System</p>
          <p>Version 2.0.0</p>
        </div>

        <div class="section">
          <h2>Getting Started</h2>
          <p>The Munbon External API provides aggregated data from multiple internal services through a single, unified interface. This API is designed for external clients, mobile applications, and third-party integrations.</p>
          
          <h3>Base URL</h3>
          <div class="code">
            Production: https://api.munbon.go.th<br>
            Staging: https://api-staging.munbon.go.th<br>
            Development: http://localhost:8000
          </div>

          <h3>Authentication</h3>
          <p>All API requests (except public endpoints) require an API key to be included in the request headers:</p>
          <div class="code">x-api-key: YOUR_API_KEY</div>

          <a href="/api-docs" class="btn">View Interactive API Documentation</a>
        </div>

        <div class="section">
          <h2>Rate Limits</h2>
          <p>API usage is subject to rate limiting to ensure fair usage and system stability:</p>
          
          <div class="api-key-tiers">
            <div class="tier-card" style="max-width: 400px; margin: 0 auto;">
              <h4>Standard Rate Limit</h4>
              <div class="limit">1,000</div>
              <div class="period">requests per 15 minutes</div>
              <p style="margin-top: 1rem; color: #718096;">Rate limits apply per API key or authenticated user</p>
            </div>
          </div>
        </div>

        <div class="section">
          <h2>Available Endpoints</h2>
          
          <h3>Public Endpoints (No Authentication)</h3>
          <div class="endpoints-grid">
            <div class="endpoint">
              <span class="method get">GET</span>
              <span class="path">/health</span>
            </div>
            <div class="endpoint">
              <span class="method get">GET</span>
              <span class="path">/api/v1/status</span>
            </div>
          </div>

          <h3>Dashboard Endpoints</h3>
          <div class="endpoints-grid">
            <div class="endpoint">
              <span class="method get">GET</span>
              <span class="path">/api/v1/dashboard/summary</span>
            </div>
            <div class="endpoint">
              <span class="method get">GET</span>
              <span class="path">/api/v1/dashboard/sensors/status</span>
            </div>
            <div class="endpoint">
              <span class="method get">GET</span>
              <span class="path">/api/v1/dashboard/alerts</span>
            </div>
          </div>

          <h3>Sensor Data Endpoints</h3>
          <div class="endpoints-grid">
            <div class="endpoint">
              <span class="method get">GET</span>
              <span class="path">/api/v1/sensors/water-level/latest</span>
            </div>
            <div class="endpoint">
              <span class="method get">GET</span>
              <span class="path">/api/v1/sensors/water-level/timeseries</span>
            </div>
            <div class="endpoint">
              <span class="method get">GET</span>
              <span class="path">/api/v1/sensors/moisture/latest</span>
            </div>
            <div class="endpoint">
              <span class="method get">GET</span>
              <span class="path">/api/v1/sensors/weather/current</span>
            </div>
          </div>

          <h3>Analytics Endpoints</h3>
          <div class="endpoints-grid">
            <div class="endpoint">
              <span class="method get">GET</span>
              <span class="path">/api/v1/analytics/water-demand</span>
            </div>
            <div class="endpoint">
              <span class="method get">GET</span>
              <span class="path">/api/v1/analytics/irrigation-schedule</span>
            </div>
            <div class="endpoint">
              <span class="method post">POST</span>
              <span class="path">/api/v1/analytics/calculate-eto</span>
            </div>
          </div>
        </div>

        <div class="section">
          <h2>Example Request</h2>
          <p>Get the latest water level readings for Zone 1:</p>
          <div class="code">
curl -H "x-api-key: YOUR_API_KEY" \\
  "https://api.munbon.go.th/api/v1/sensors/water-level/latest?zone=Z1"
          </div>

          <h3>Example Response</h3>
          <div class="code">
{
  "success": true,
  "data": {
    "data_type": "water_level",
    "sensor_count": 5,
    "sensors": [
      {
        "sensor_id": "WL001",
        "sensor_name": "Water Level Sensor 1",
        "location": {
          "latitude": 15.2296,
          "longitude": 104.8574
        },
        "zone": "Z1",
        "latest_reading": {
          "timestamp": "2024-07-08T10:30:00Z",
          "timestamp_buddhist": "08/07/2567",
          "water_level_m": 2.45,
          "flow_rate_m3s": 0.85,
          "quality": 98.5
        }
      }
    ]
  },
  "meta": {
    "timestamp": "2024-07-08T10:35:00Z",
    "version": "2.0.0",
    "requestId": "req_abc123",
    "cached": false
  }
}
          </div>
        </div>

        <div class="section">
          <h2>SDKs and Libraries</h2>
          <p>Official SDKs are available for the following languages:</p>
          <ul style="margin-left: 2rem;">
            <li>JavaScript/TypeScript (Node.js)</li>
            <li>Python</li>
            <li>Java</li>
            <li>Go</li>
          </ul>
          <p style="margin-top: 1rem;">Visit our <a href="https://github.com/munbon/api-sdks" style="color: #2b6cb0;">GitHub repository</a> for SDK documentation and examples.</p>
        </div>

        <div class="section">
          <h2>Support</h2>
          <p>For API support, please contact:</p>
          <ul style="margin-left: 2rem;">
            <li>Email: <a href="mailto:api@munbon.go.th" style="color: #2b6cb0;">api@munbon.go.th</a></li>
            <li>Documentation: <a href="/api-docs" style="color: #2b6cb0;">Interactive API Docs</a></li>
            <li>Status Page: <a href="https://status.munbon.go.th" style="color: #2b6cb0;">status.munbon.go.th</a></li>
          </ul>
        </div>
      </div>
    </body>
    </html>
  `);
});

// Serve Swagger UI
app.use('/api-docs', swaggerUi.serve, swaggerUi.setup(openapiDocument, swaggerOptions));

// Serve OpenAPI spec as JSON
app.get('/openapi.json', (req, res) => {
  res.json(openapiDocument);
});

// Serve OpenAPI spec as YAML
app.get('/openapi.yaml', (req, res) => {
  res.type('text/yaml');
  res.sendFile(openapiPath);
});

// Start server
const PORT = process.env.DOCS_PORT || 3100;
app.listen(PORT, () => {
  console.log(`API Documentation Portal running on port ${PORT}`);
  console.log(`View documentation at http://localhost:${PORT}`);
  console.log(`Interactive API docs at http://localhost:${PORT}/api-docs`);
});