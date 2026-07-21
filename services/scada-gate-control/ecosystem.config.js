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
        // PR 7.2 independent physical-write gate. Pilot enablement is an
        // out-of-band operational change; tracked configuration stays dark.
        ALLOW_MACHINE_COMMANDS: 'false',
      },
    },
  ],
};
