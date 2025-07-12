module.exports = {
  apps: [
    // =================
    // API Services
    // =================
    
    // Unified API - Simple data retrieval API
    {
      name: 'unified-api',
      script: 'src/unified-api.js',
      cwd: './services/sensor-data',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '500M',
      env: {
        PORT: 3000,
        NODE_ENV: 'development',
        INTERNAL_API_KEY: 'munbon-internal-f3b89263126548',
        // PostgreSQL connection (outside Docker → Docker on port 5434)
        POSTGRES_HOST: 'localhost',
        POSTGRES_PORT: 5434,
        POSTGRES_DB: 'munbon_dev',
        POSTGRES_USER: 'postgres',
        POSTGRES_PASSWORD: 'postgres',
        // TimescaleDB connection (outside Docker → Docker)
        TIMESCALE_HOST: 'localhost',
        TIMESCALE_PORT: 5433,
        TIMESCALE_DB: 'munbon_timescale',
        TIMESCALE_USER: 'postgres',
        TIMESCALE_PASSWORD: 'postgres'
      }
    },
    
    // Sensor Data Service - Full TypeScript microservice for ingestion
    {
      name: 'sensor-data-service',
      script: 'npm',
      args: 'run dev',
      cwd: './services/sensor-data',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '1G',
      env: {
        PORT: 3003,
        NODE_ENV: 'development',
        // TimescaleDB connection
        TIMESCALE_HOST: 'localhost',
        TIMESCALE_PORT: 5433,
        TIMESCALE_DB: 'sensor_data',
        TIMESCALE_USER: 'postgres',
        TIMESCALE_PASSWORD: 'postgres',
        // Valid tokens for ingestion
        VALID_TOKENS: 'munbon-ridr-water-level:water-level,munbon-m2m-moisture:moisture',
        EXTERNAL_API_KEYS: 'rid-ms-dev-1234567890abcdef,test-key-fedcba0987654321',
        // MQTT settings
        MQTT_BROKER_URL: 'mqtt://localhost:1883',
        // Redis
        REDIS_URL: 'redis://localhost:6379'
      }
    },
    // =================
    // Infrastructure Tools
    // =================
    
    // Cloudflare Tunnel - Exposes local API to internet
    {
      name: 'cloudflare-tunnel',
      script: 'cloudflared',
      args: 'tunnel --url http://localhost:3000',
      interpreter: 'none',
      autorestart: true,
      watch: false,
      env: {
        NODE_ENV: 'development'
      },
      error_file: './logs/tunnel-error.log',
      out_file: './logs/tunnel-out.log'
    },
    
    // Cloudflare Tunnel for External API - Provides legacy TLS/cipher support
    {
      name: 'cloudflare-tunnel-external',
      script: 'cloudflared',
      args: 'tunnel --url https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com',
      interpreter: 'none',
      autorestart: true,
      watch: false,
      env: {
        NODE_ENV: 'development',
        TUNNEL_METRICS: '0.0.0.0:2001'  // Different metrics port to avoid conflict
      },
      error_file: './logs/tunnel-external-error.log',
      out_file: './logs/tunnel-external-out.log',
      // Post-start script to extract and save tunnel URL
      post_deploy: 'sleep 5 && grep -o "https://[a-zA-Z0-9\\-]*\\.trycloudflare\\.com" ./logs/tunnel-external-out.log | tail -1 > ./services/sensor-data/tunnel-external-url.txt'
    },
    
    // Tunnel Monitor - Updates AWS Parameter Store with tunnel URL
    {
      name: 'tunnel-monitor',
      script: './services/sensor-data/auto-update-tunnel.sh',
      interpreter: 'bash',
      autorestart: true,
      watch: false,
      env: {
        NODE_ENV: 'development',
        AWS_REGION: 'ap-southeast-1'
      },
      error_file: './logs/tunnel-monitor-error.log',
      out_file: './logs/tunnel-monitor-out.log'
    },
    
    // External Tunnel Monitor - Monitors and displays external API tunnel URL
    {
      name: 'external-tunnel-monitor',
      script: 'bash',
      args: '-c "while true; do if [ -f ./logs/tunnel-external-out.log ]; then URL=$(grep -o \'https://[a-zA-Z0-9\\-]*\\.trycloudflare\\.com\' ./logs/tunnel-external-out.log | tail -1); if [ -n \\"$URL\\" ]; then echo \\"External API Tunnel URL: $URL\\"; echo \\"$URL\\" > ./services/sensor-data/tunnel-external-url.txt; fi; fi; sleep 60; done"',
      interpreter: '/bin/bash',
      autorestart: true,
      watch: false,
      env: {
        NODE_ENV: 'development'
      },
      error_file: './logs/external-tunnel-monitor-error.log',
      out_file: './logs/external-tunnel-monitor-out.log'
    },
    
    // =================
    // Background Workers
    // =================
    
    // Sensor Data Consumer - Processes sensor data from SQS
    {
      name: 'sensor-consumer',
      script: 'npm',
      args: 'run consumer',
      cwd: './services/sensor-data',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '500M',
      env: {
        NODE_ENV: 'development',
        AWS_REGION: 'ap-southeast-1',
        // TimescaleDB connection
        TIMESCALE_HOST: 'localhost',
        TIMESCALE_PORT: 5433,
        TIMESCALE_DB: 'munbon_timescale',
        TIMESCALE_USER: 'postgres',
        TIMESCALE_PASSWORD: 'postgres',
        // SQS Queue URL (if needed)
        SQS_QUEUE_URL: process.env.SQS_QUEUE_URL || '',
        // Consumer port
        CONSUMER_PORT: 3004
      },
      error_file: './logs/sensor-consumer-error.log',
      out_file: './logs/sensor-consumer-out.log'
    },
    
    // =================
    // GIS Services
    // =================
    
    // GIS API Service - Handles shapefile uploads and spatial queries
    {
      name: 'gis-api',
      script: 'npm',
      args: 'run dev',
      cwd: './services/gis',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '1G',
      env: {
        PORT: 3007,
        NODE_ENV: 'development',
        // PostgreSQL/PostGIS connection
        POSTGRES_HOST: 'localhost',
        POSTGRES_PORT: 5434,
        POSTGRES_DB: 'munbon_dev',
        POSTGRES_USER: 'postgres',
        POSTGRES_PASSWORD: 'postgres'
      },
      error_file: './logs/gis-api-error.log',
      out_file: './logs/gis-api-out.log'
    },
    
    // GIS Queue Processor - Processes shapefile uploads from SQS
    {
      name: 'gis-queue-processor',
      script: 'npm',
      args: 'run queue:processor',
      cwd: './services/gis',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '500M',
      env: {
        NODE_ENV: 'development',
        AWS_REGION: 'ap-southeast-1',
        // PostgreSQL/PostGIS connection
        POSTGRES_HOST: 'localhost',
        POSTGRES_PORT: 5434,
        POSTGRES_DB: 'munbon_dev',
        POSTGRES_USER: 'postgres',
        POSTGRES_PASSWORD: 'postgres',
        // SQS Queue URL (if needed)
        GIS_QUEUE_URL: process.env.GIS_QUEUE_URL || ''
      },
      error_file: './logs/gis-queue-error.log',
      out_file: './logs/gis-queue-out.log'
    },
    
    // =================
    // Auth Service (Enable when needed)
    // =================
    
    // Uncomment to enable authentication service
    // {
    //   name: 'auth-service',
    //   script: 'npm',
    //   args: 'run dev',
    //   cwd: './services/auth',
    //   instances: 1,
    //   autorestart: true,
    //   watch: false,
    //   max_memory_restart: '500M',
    //   env: {
    //     PORT: 3001,
    //     NODE_ENV: 'development',
    //     DATABASE_URL: 'postgresql://postgres:postgres@localhost:5434/munbon_dev',
    //     REDIS_URL: 'redis://localhost:6379',
    //     JWT_SECRET: 'local-dev-secret-change-in-production',
    //     SESSION_SECRET: 'local-session-secret-change-in-production'
    //   },
    //   error_file: './logs/auth-service-error.log',
    //   out_file: './logs/auth-service-out.log'
    // }
  ]
};