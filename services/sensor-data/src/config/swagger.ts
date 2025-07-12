import swaggerJsdoc from 'swagger-jsdoc';

const options: swaggerJsdoc.Options = {
  definition: {
    openapi: '3.0.0',
    info: {
      title: 'Munbon Sensor Data API',
      version: '1.0.0',
      description: 'REST API for accessing sensor data from water level and moisture sensors in the Munbon Irrigation Project',
      contact: {
        name: 'Munbon API Support',
        email: 'api@munbon.th'
      }
    },
    servers: [
      {
        url: 'http://localhost:3001',
        description: 'Development server'
      },
      {
        url: 'https://api.munbon.th',
        description: 'Production server'
      }
    ],
    components: {
      securitySchemes: {
        apiKey: {
          type: 'apiKey',
          in: 'header',
          name: 'X-API-Key',
          description: 'API key for external system access (RID-MS)'
        },
        bearerAuth: {
          type: 'http',
          scheme: 'bearer',
          bearerFormat: 'JWT',
          description: 'JWT token for authenticated endpoints'
        }
      },
      schemas: {
        Sensor: {
          type: 'object',
          properties: {
            id: { type: 'string', example: 'RIDR001' },
            type: { 
              type: 'string', 
              enum: ['water-level', 'moisture'],
              example: 'water-level' 
            },
            name: { type: 'string', example: 'Water Level Sensor 1' },
            description: { type: 'string' },
            manufacturer: { type: 'string', example: 'RID-R' },
            location: {
              type: 'object',
              properties: {
                lat: { type: 'number', example: 13.7563 },
                lng: { type: 'number', example: 100.5018 }
              }
            },
            isActive: { type: 'boolean', example: true },
            lastSeen: { type: 'string', format: 'date-time' },
            metadata: { type: 'object' },
            totalReadings: { type: 'integer', example: 1234 },
            createdAt: { type: 'string', format: 'date-time' },
            updatedAt: { type: 'string', format: 'date-time' }
          }
        },
        WaterLevelReading: {
          type: 'object',
          properties: {
            sensorId: { type: 'string', example: 'RIDR001' },
            sensorName: { type: 'string' },
            timestamp: { type: 'string', format: 'date-time' },
            levelCm: { type: 'number', example: 15.5 },
            voltage: { type: 'number', example: 3.85 },
            rssi: { type: 'integer', example: -65 },
            temperature: { type: 'number' },
            location: {
              type: 'object',
              properties: {
                lat: { type: 'number' },
                lng: { type: 'number' }
              }
            },
            qualityScore: { type: 'number', example: 0.95 }
          }
        },
        MoistureReading: {
          type: 'object',
          properties: {
            sensorId: { type: 'string', example: '00001-00001' },
            sensorName: { type: 'string' },
            timestamp: { type: 'string', format: 'date-time' },
            moistureSurfacePct: { type: 'number', example: 45 },
            moistureDeepPct: { type: 'number', example: 58 },
            tempSurfaceC: { type: 'number', example: 28.5 },
            tempDeepC: { type: 'number', example: 27.0 },
            ambientHumidityPct: { type: 'number', example: 65 },
            ambientTempC: { type: 'number', example: 32.5 },
            floodStatus: { type: 'boolean', example: false },
            voltage: { type: 'number', example: 3.9 },
            location: {
              type: 'object',
              properties: {
                lat: { type: 'number' },
                lng: { type: 'number' }
              }
            },
            qualityScore: { type: 'number', example: 1.0 }
          }
        },
        Pagination: {
          type: 'object',
          properties: {
            page: { type: 'integer', example: 1 },
            limit: { type: 'integer', example: 20 },
            total: { type: 'integer', example: 100 },
            totalPages: { type: 'integer', example: 5 }
          }
        },
        Error: {
          type: 'object',
          properties: {
            error: { type: 'string' },
            message: { type: 'string' },
            statusCode: { type: 'integer' }
          }
        }
      }
    }
  },
  apis: ['./src/routes/*.ts', './src/routes/*.routes.ts']
};

export const swaggerSpec = swaggerJsdoc(options);