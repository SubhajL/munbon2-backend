module.exports = {
  apps: [
    {
      name: 'gis-api',
      script: 'npm',
      args: 'run dev',
      cwd: './',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '1G',
      env: {
        NODE_ENV: 'development',
        PORT: 3007
      },
      error_file: './logs/gis-api-error.log',
      out_file: './logs/gis-api-out.log',
      log_file: './logs/gis-api-combined.log',
      time: true
    },
    {
      name: 'gis-queue-processor',
      script: 'npm',
      args: 'run queue:processor',
      cwd: './',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '500M',
      env: {
        NODE_ENV: 'development'
      },
      error_file: './logs/gis-queue-error.log',
      out_file: './logs/gis-queue-out.log',
      log_file: './logs/gis-queue-combined.log',
      time: true
    }
  ]
};