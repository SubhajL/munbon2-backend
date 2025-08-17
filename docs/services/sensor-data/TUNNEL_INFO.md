# Cloudflare Tunnel Information

## Permanent Tunnel Details
- **Tunnel Name**: munbon-api
- **Tunnel ID**: f3b89263-1265-4843-b08c-5391e73e8c75
- **Permanent URL**: https://f3b89263-1265-4843-b08c-5391e73e8c75.cfargotunnel.com
- **Status**: ✅ Active and permanent

## How to Run
```bash
# Start tunnel
cloudflared tunnel run munbon-api

# Or run in background with nohup
nohup cloudflared tunnel run munbon-api > tunnel.log 2>&1 &

# Or use screen/tmux
screen -S tunnel
cloudflared tunnel run munbon-api
# Press Ctrl+A, D to detach
```

## Make it Permanent (Auto-start)
```bash
# Option 1: macOS service
sudo cloudflared service install
sudo cloudflared service start

# Option 2: Using PM2
npm install -g pm2
pm2 start cloudflared --name tunnel -- tunnel run munbon-api
pm2 save
pm2 startup
```

## Testing
```bash
# Test if tunnel is working
curl https://f3b89263-1265-4843-b08c-5391e73e8c75.cfargotunnel.com

# Should return error until we start local API on port 3000
```

## Important
- This URL is permanent and will always work when tunnel is running
- No expiration, no limits
- Completely free forever