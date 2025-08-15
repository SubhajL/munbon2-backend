module.exports = {
  apps: [{
    name: 'sensor-location-mapping',
    script: './dist/main.js',
    instances: 1,
    exec_mode: 'cluster',
    env: {
      NODE_ENV: 'production',
      PORT: 3018,
      // Database connections (using localhost since service runs on EC2)
      TIMESCALE_HOST: 'localhost',
      TIMESCALE_PORT: 5432,
      TIMESCALE_DB: 'sensor_data',
      TIMESCALE_USER: 'postgres',
      TIMESCALE_PASSWORD: 'postgres123',
      POSTGIS_HOST: 'localhost',
      POSTGIS_PORT: 5432,
      POSTGIS_DB: 'gis_db',
      POSTGIS_USER: 'postgres',
      POSTGIS_PASSWORD: 'postgres123'
    },
    error_file: '/home/ubuntu/logs/sensor-location-mapping-error.log',
    out_file: '/home/ubuntu/logs/sensor-location-mapping-out.log',
    log_file: '/home/ubuntu/logs/sensor-location-mapping-combined.log',
    time: true,
    max_memory_restart: '500M',
    autorestart: true,
    max_restarts: 10,
    min_uptime: '10s',
    watch: false,
    ignore_watch: ['node_modules', 'logs'],
    merge_logs: true,
    kill_timeout: 5000,
    listen_timeout: 5000,
    log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
  }]
};