module.exports = {
  apps: [{
    name: 'shapefile-queue-processor',
    script: './dist/workers/shapefile-queue-processor.js',
    instances: 1,
    exec_mode: 'fork',
    env: {
      NODE_ENV: 'production',
      DATABASE_URL: 'postgresql://postgres:postgres@localhost:5432/munbon_dev',
      DATABASE_SSL: 'false',
      GIS_SCHEMA: 'gis',
      DB_POOL_SIZE: '10',
      DB_POOL_IDLE_TIMEOUT: '30000',
      ENABLE_QUERY_LOGGING: 'false',
      AWS_REGION: 'ap-southeast-1',
      AWS_ACCOUNT_ID: '108728974441',
      GIS_SQS_QUEUE_URL: 'https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-gis-shapefile-queue',
      SHAPE_FILE_BUCKET: 'munbon-gis-shape-files',
      EXTERNAL_UPLOAD_TOKEN: 'munbon-gis-shapefile',
      REDIS_URL: 'redis://localhost:6379',
      LOG_LEVEL: 'info'
    },
    max_memory_restart: '1G',
    error_file: '~/.pm2/logs/shapefile-queue-error.log',
    out_file: '~/.pm2/logs/shapefile-queue-out.log',
    merge_logs: true,
    time: true
  }]
};