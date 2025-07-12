require('dotenv').config();

async function testProcessor() {
  // First connect to database
  const { AppDataSource } = require('./dist/config/database');
  
  console.log('Initializing database...');
  await AppDataSource.initialize();
  console.log('Database initialized');
  
  // Create schema if needed
  await AppDataSource.query('CREATE SCHEMA IF NOT EXISTS gis');
  console.log('Schema ready');
  
  // Synchronize
  await AppDataSource.synchronize();
  console.log('Tables synchronized');
  
  // Now test the service
  const { ShapeFileService } = require('./dist/services/shapefile.service');
  const service = new ShapeFileService();
  
  const testMessage = {
    uploadId: '1584d9cf-1246-4bb0-8f4c-066a39e4f637',
    s3Bucket: 'munbon-gis-shape-files',
    s3Key: 'shape-files/2025-07-01/1584d9cf-1246-4bb0-8f4c-066a39e4f637/test-shapefile.zip',
    fileName: 'test-shapefile.zip',
    waterDemandMethod: 'RID-MS'
  };
  
  try {
    console.log('Processing message...');
    await service.processShapeFileFromQueue(testMessage);
    console.log('Success!');
  } catch (error) {
    console.error('Processing error:', error.message);
    console.error('Stack:', error.stack);
  }
  
  await AppDataSource.destroy();
}

// Compile TypeScript first
const { execSync } = require('child_process');
console.log('Building TypeScript...');
execSync('npm run build', { stdio: 'inherit' });

testProcessor().catch(console.error);