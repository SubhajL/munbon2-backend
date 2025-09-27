module.exports = {
  apps: [{
    name: 'geopackage-processor',
    script: './geopackage-processor-worker.js',
    instances: 1,
    exec_mode: 'fork',  // Change from cluster to fork mode
    autorestart: true,
    watch: false,
    max_memory_restart: '1G',
    error_file: '/home/ubuntu/.pm2/logs/geopackage-processor-error.log',
    out_file: '/home/ubuntu/.pm2/logs/geopackage-processor-out.log',
    log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
    env: {
      NODE_ENV: 'production',
      POSTGRES_PASSWORD: 'P@ssw0rd123!',
      UPLOAD_DIR: '/home/ubuntu/geopackage-uploads',
      TEMP_DIR: '/tmp/geopackage-processing',
      PROCESSED_DIR: '/home/ubuntu/geopackage-processed',
      POLL_INTERVAL: '30000', // 30 seconds
      BATCH_SIZE: '1000',
      MAX_RETRIES: '3'
    }
  }]
};