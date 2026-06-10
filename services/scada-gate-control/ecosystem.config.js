module.exports = {
  apps: [
    {
      name: 'scada-gate-control',
      script: 'dist/index.js',
      cwd: __dirname,
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '256M',
      env: {
        NODE_ENV: 'production',
        TZ: 'Asia/Bangkok',
      },
    },
  ],
};
