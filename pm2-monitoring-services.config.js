module.exports = {
  apps: [
    // =================
    // Monitoring Services
    // =================
    
    // Water Level Monitoring Service - Port 3008
    {
      name: 'water-level-monitoring',
      script: 'npm',
      args: 'run dev',
      cwd: './services/water-level-monitoring',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '500M',
      env: {
        PORT: 3008,
        NODE_ENV: 'development',
        // TimescaleDB connection
        TIMESCALE_HOST: 'localhost',
        TIMESCALE_PORT: 5433,
        TIMESCALE_DATABASE: 'munbon_timescale',
        TIMESCALE_USER: 'postgres',
        TIMESCALE_PASSWORD: 'postgres',
        // Redis
        REDIS_HOST: 'localhost',
        REDIS_PORT: 6379,
        REDIS_DB: 2,
        // MQTT
        MQTT_BROKER_URL: 'mqtt://localhost:1883',
        MQTT_CLIENT_ID: 'water-level-monitoring-service'
      },
      error_file: './logs/water-level-error.log',
      out_file: './logs/water-level-out.log'
    },
    
    // Moisture Monitoring Service - Port 3005
    {
      name: 'moisture-monitoring',
      script: 'npm',
      args: 'run dev',
      cwd: './services/moisture-monitoring',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '500M',
      env: {
        PORT: 3005,
        NODE_ENV: 'development',
        // TimescaleDB connection
        TIMESCALE_HOST: 'localhost',
        TIMESCALE_PORT: 5433,
        TIMESCALE_DATABASE: 'munbon_timescale',
        TIMESCALE_USER: 'postgres',
        TIMESCALE_PASSWORD: 'postgres',
        // Redis
        REDIS_HOST: 'localhost',
        REDIS_PORT: 6379,
        REDIS_DB: 3,
        // MQTT
        MQTT_BROKER_URL: 'mqtt://localhost:1883',
        MQTT_CLIENT_ID: 'moisture-monitoring-service'
      },
      error_file: './logs/moisture-error.log',
      out_file: './logs/moisture-out.log'
    },
    
    // Weather Monitoring Service - Port 3006 (FIXED from 3047)
    {
      name: 'weather-monitoring',
      script: 'npm',
      args: 'run dev',
      cwd: './services/weather-monitoring',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '500M',
      env: {
        PORT: 3006,
        NODE_ENV: 'development',
        // TimescaleDB connection
        TIMESCALE_HOST: 'localhost',
        TIMESCALE_PORT: 5433,
        TIMESCALE_DATABASE: 'munbon_timescale',
        TIMESCALE_USER: 'postgres',
        TIMESCALE_PASSWORD: 'postgres',
        // PostgreSQL
        POSTGRES_HOST: 'localhost',
        POSTGRES_PORT: 5434,
        POSTGRES_DATABASE: 'munbon_dev',
        POSTGRES_USER: 'postgres',
        POSTGRES_PASSWORD: 'postgres',
        // Redis
        REDIS_HOST: 'localhost',
        REDIS_PORT: 6379,
        REDIS_DB: 4,
        // MQTT
        MQTT_BROKER_URL: 'mqtt://localhost:1883',
        MQTT_CLIENT_ID: 'weather-monitoring-service'
      },
      error_file: './logs/weather-error.log',
      out_file: './logs/weather-out.log'
    },
    
    // ROS Service - Port 3047 (NO CONFLICT NOW)
    {
      name: 'ros-service',
      script: 'npm',
      args: 'run dev',
      cwd: './services/ros',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '500M',
      env: {
        PORT: 3047,
        NODE_ENV: 'development',
        // PostgreSQL connection
        POSTGRES_HOST: 'localhost',
        POSTGRES_PORT: 5434,
        POSTGRES_DATABASE: 'munbon_dev',
        POSTGRES_USER: 'postgres',
        POSTGRES_PASSWORD: 'postgres',
        // Redis
        REDIS_HOST: 'localhost',
        REDIS_PORT: 6379,
        REDIS_DB: 5
      },
      error_file: './logs/ros-error.log',
      out_file: './logs/ros-out.log'
    }
  ]
};