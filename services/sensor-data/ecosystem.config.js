module.exports = {
  apps: [
    {
      name: 'sensor-api',
      script: 'src/unified-api.js',
      cwd: '/Users/subhajlimanond/dev/munbon2-backend/services/sensor-data',
      env: {
        PORT: 3000,
        INTERNAL_API_KEY: 'munbon-internal-f3b89263126548'
      }
    },
    {
      name: 'cloudflare-tunnel',
      script: 'bash',
      args: '-c "cloudflared tunnel --url http://localhost:3000 2>&1 | tee tunnel.log"',
      cwd: '/Users/subhajlimanond/dev/munbon2-backend/services/sensor-data',
      interpreter: '/bin/bash',
      watch: false,
      autorestart: true,
      max_restarts: 10,
      min_uptime: '10s',
      // This runs after the tunnel starts
      post_start: [
        'sleep 5',
        'node update-tunnel-url.js'
      ]
    }
  ]
};