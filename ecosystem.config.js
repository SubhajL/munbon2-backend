module.exports = {
  apps: [
    {
      name: 'bff-water-planning',
      script: './venv/bin/python',
      args: '-m uvicorn src.main:app --host 0.0.0.0 --port 3002',
      cwd: '/Users/subhajlimanond/dev/munbon2-backend/services/bff-water-planning',
      autorestart: true,
      max_memory_restart: '512M',
      env: {
        PORT: '3002',
        HOST: '0.0.0.0',
        ENVIRONMENT: 'production',
        LOG_LEVEL: 'INFO',
        // Database URLs - update these with your actual values
        POSTGRES_URL: 'postgresql://postgres:P@ssw0rd123!@43.208.201.191:5432/munbon_dev',
        GIS_DATABASE_URL: 'postgresql://postgres:P@ssw0rd123!@43.208.201.191:5432/munbon_gis',
        TIMESCALE_URL: 'postgresql://postgres:P@ssw0rd123!@43.208.201.191:5432/sensor_data',
        // Redis
        REDIS_URL: 'redis://localhost:6379/2',
        // External Services
        ROS_SERVICE_URL: 'http://localhost:3047',
        GIS_SERVICE_URL: 'http://localhost:3007',
        AWD_CONTROL_URL: 'http://localhost:3010',
        // Mock mode
        USE_MOCK_SERVER: 'false',
      },
      error_file: '/Users/subhajlimanond/dev/munbon2-backend/logs/bff-water-planning-error.log',
      out_file: '/Users/subhajlimanond/dev/munbon2-backend/logs/bff-water-planning-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      merge_logs: true,
      time: true,
    },
    {
      name: 'smartfarm-water-control',
      script: 'src/index.js',
      cwd: '/Users/subhajlimanond/dev/munbon2-backend/services/smartfarm-water-control',
      autorestart: true,
      max_memory_restart: '256M',
      env: {
        PORT: '3050',
        // Control Loop Configuration
        CONTROL_LOOP_INTERVAL_MINUTES: '15',
        // Database Listener (Realtime Control)
        ENABLE_DB_LISTENER: 'true',
        LISTENER_RECONNECT_DELAY_MS: '5000',
        LISTENER_DEBOUNCE_WINDOW_MS: '5000',
        MOISTURE_FRESHNESS_WINDOW_MS: '300000',
        // TimescaleDB
        TIMESCALE_HOST: '43.208.201.191',
        TIMESCALE_PORT: '5432',
        TIMESCALE_USER: 'postgres',
        TIMESCALE_PASSWORD: 'P@ssw0rd123!',
        TIMESCALE_DB: 'sensor_data',
        // MSSQL (SCADA)
        MSSQL_HOST: '43.208.201.191',
        MSSQL_PORT: '1433',
        MSSQL_USER: 'sa',
        MSSQL_PASSWORD: 'P@ssw0rd123!',
        MSSQL_DB: 'db_scada',
        MSSQL_TABLE: 'tb_valve_command_v2',
        // ROS Integration
        ROS_API_URL: 'http://43.208.201.191:3047',
        ROS_API_KEY: '',
        ROS_ENDPOINT: '/api/daily-demands',
        // Plot Configuration (will be loaded from database)
        // Logging
        LOG_LEVEL: 'info',
      },
      error_file: '/Users/subhajlimanond/dev/munbon2-backend/logs/smartfarm-water-control-error.log',
      out_file: '/Users/subhajlimanond/dev/munbon2-backend/logs/smartfarm-water-control-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      merge_logs: true,
      time: true,
    },
  ],
};
