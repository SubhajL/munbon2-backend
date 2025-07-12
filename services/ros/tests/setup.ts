import dotenv from 'dotenv';

// Load test environment variables
dotenv.config({ path: '.env.test' });

// Set test environment
process.env.NODE_ENV = 'test';

// Mock Redis client
jest.mock('../src/config/redis', () => ({
  connectRedis: jest.fn().mockResolvedValue({}),
  getRedisClient: jest.fn().mockReturnValue({
    get: jest.fn(),
    set: jest.fn(),
    setex: jest.fn(),
    del: jest.fn(),
    ping: jest.fn().mockResolvedValue('PONG')
  })
}));

// Increase timeout for database operations
jest.setTimeout(30000);

// Global test utilities
global.testUtils = {
  generateMockCalculationInput: () => ({
    cropType: 'ข้าว กข.(นาดำ)',
    plantings: [{
      plantingDate: new Date('2024-11-01'),
      areaRai: 1000
    }],
    calculationDate: new Date('2024-12-15'),
    calculationPeriod: 'daily' as const,
    nonAgriculturalDemands: {
      domestic: 5000,
      industrial: 2000
    }
  })
};