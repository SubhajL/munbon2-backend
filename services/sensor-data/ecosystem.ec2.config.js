module.exports = {
  apps: [{
    name: 'sqs-consumer',
    script: './dist/cmd/consumer/main.js',
    env: {
      NODE_ENV: 'production',
      TIMESCALE_HOST: 'localhost',
      TIMESCALE_PORT: '5432',
      TIMESCALE_DB: 'sensor_data',
      TIMESCALE_USER: 'postgres',
      TIMESCALE_PASSWORD: process.env.TIMESCALE_PASSWORD || (() => { throw new Error('TIMESCALE_PASSWORD env var is required (hardcoded default removed; SEC remediation)'); })(),
      SQS_QUEUE_URL: 'https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-sensor-ingestion-dev-queue',
      AWS_REGION: 'ap-southeast-1',
      LOG_LEVEL: 'debug'
    }
  }]
};