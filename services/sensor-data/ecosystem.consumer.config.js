module.exports = {
  apps: [{
    name: 'sensor-consumer',
    script: 'npm',
    args: 'run consumer',
    cwd: '/Users/subhajlimanond/dev/munbon2-backend/services/sensor-data',
    env: {
      NODE_ENV: 'production',
      AWS_REGION: 'ap-southeast-1',
      SQS_QUEUE_URL: 'https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-sensor-ingestion-dev-queue',
      TIMESCALE_HOST: 'localhost',
      TIMESCALE_PORT: '5433',
      TIMESCALE_DB: 'munbon_timescale',
      TIMESCALE_USER: 'postgres',
      TIMESCALE_PASSWORD: 'postgres',
      CONSUMER_PORT: '3004'
    },
    instances: 1,
    autorestart: true,
    watch: false,
    max_memory_restart: '1G',
    log_date_format: 'YYYY-MM-DD HH:mm:ss',
    error_file: 'logs/sensor-consumer-error.log',
    out_file: 'logs/sensor-consumer-out.log',
    merge_logs: true,
    min_uptime: '10s',
    max_restarts: 10,
    restart_delay: 4000
  }]
};