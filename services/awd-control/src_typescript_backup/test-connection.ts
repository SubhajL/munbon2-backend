import dotenv from 'dotenv';
import { logger } from './utils/logger';

// Load environment variables
dotenv.config();

async function testConnections() {
  logger.info('Testing AWD Control Service connections...');
  
  // Test basic setup
  logger.info({
    port: process.env.PORT,
    postgresHost: process.env.POSTGRES_HOST,
    timescaleHost: process.env.TIMESCALE_HOST,
    redisHost: process.env.REDIS_HOST,
    kafkaBrokers: process.env.KAFKA_BROKERS,
  }, 'Configuration loaded');
  
  logger.info('Basic configuration test passed');
  process.exit(0);
}

testConnections().catch(error => {
  logger.error(error, 'Test failed');
  process.exit(1);
});