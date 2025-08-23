import { ShapeFileProcessor } from '../processors/shape-file-processor';
import * as dotenv from 'dotenv';
import * as path from 'path';

// Load environment variables
dotenv.config({ path: path.join(__dirname, '../../.env') });

async function testProcessor() {
  console.log('Testing Shape File Processor...');
  console.log('Environment:', {
    DATABASE_URL: process.env.DATABASE_URL ? 'Set' : 'Not set',
    AWS_REGION: process.env.AWS_REGION,
    SQS_QUEUE_URL: process.env.SQS_QUEUE_URL ? 'Set' : 'Not set',
    SHAPE_FILE_BUCKET: process.env.SHAPE_FILE_BUCKET,
  });

  // Create processor instance
  const processor = new ShapeFileProcessor();

  // Test database connection
  try {
    console.log('\nTesting database connection...');
    // This will fail if database is not available, which is expected for now
    await processor.start();
    
    // Run for 30 seconds then stop
    setTimeout(async () => {
      console.log('\nStopping processor...');
      await processor.stop();
      process.exit(0);
    }, 30000);
  } catch (error) {
    console.error('Test failed:', error);
    process.exit(1);
  }
}

// Run test
testProcessor().catch(console.error);