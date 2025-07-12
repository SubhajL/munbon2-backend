# Permanent Cloudflare Tunnel for Mock API Server

## Why Permanent Tunnel?

The temporary tunnels have these issues:
- Disconnect after ~6-8 hours
- URL changes on every restart  
- Connection drops randomly
- No retry mechanism
- Can't survive system reboots

## Solution: Permanent Tunnel with Auto-Recovery

### Method 1: PM2 Process Manager (Recommended)

PM2 provides automatic restart, logging, and monitoring.

```bash
# 1. Install PM2 globally
npm install -g pm2

# 2. Set up permanent tunnel
cd api-contracts
./setup-permanent-mock-tunnel.sh

# 3. Start with PM2
pm2 start ~/.cloudflared/mock-tunnel-pm2.json

# 4. Save PM2 configuration
pm2 save
pm2 startup  # Follow the instructions to enable startup

# 5. Monitor
pm2 monit  # Real-time monitoring
pm2 logs   # View logs
```

### Method 2: Docker Compose (Most Reliable)

Docker ensures consistent environment and easy recovery.

```bash
# 1. Update tunnel ID in cloudflared-mock-config.yml
# Replace YOUR_TUNNEL_ID_HERE with actual ID

# 2. Start services
docker-compose -f docker-compose.mock-tunnel.yml up -d

# 3. Check status
docker-compose -f docker-compose.mock-tunnel.yml ps
docker-compose -f docker-compose.mock-tunnel.yml logs -f
```

### Method 3: System Service (Auto-start on boot)

**macOS (launchd):**
```bash
# Setup and load
./setup-permanent-mock-tunnel.sh
launchctl load ~/Library/LaunchAgents/com.munbon.mock-tunnel.plist

# Check status
launchctl list | grep munbon
```

**Linux (systemd):**
```bash
# Setup and enable
./setup-permanent-mock-tunnel.sh
systemctl --user enable munbon-mock-tunnel
systemctl --user start munbon-mock-tunnel

# Check status
systemctl --user status munbon-mock-tunnel
```

## Getting a Stable URL

### Option 1: Free Domain + Cloudflare

1. Get free domain from [Freenom](https://freenom.com) (.tk, .ml, .ga)
2. Add to Cloudflare (free account)
3. Create DNS route:
   ```bash
   cloudflared tunnel route dns munbon-mock-api mock-api.yourdomain.tk
   ```

### Option 2: Subdomain on Existing Domain

If you have any domain in Cloudflare:
```bash
cloudflared tunnel route dns munbon-mock-api mock-api.existing-domain.com
```

### Option 3: Use Tunnel UUID URL

Without DNS setup, you get a stable UUID URL:
```
https://YOUR-TUNNEL-ID.cfargotunnel.com
```

Less friendly but permanent and stable.

## Troubleshooting

### Check Tunnel Status
```bash
# List tunnels
cloudflared tunnel list

# Check specific tunnel
cloudflared tunnel info munbon-mock-api

# View tunnel logs
tail -f ~/.cloudflared/tunnel-*.log
```

### Common Issues

1. **Port 4010 already in use**
   ```bash
   lsof -i :4010
   kill -9 <PID>
   ```

2. **Tunnel won't start**
   - Check credentials: `ls ~/.cloudflared/*.json`
   - Verify config: `cat ~/.cloudflared/mock-api-config.yml`
   - Re-login: `cloudflared tunnel login`

3. **Connection drops**
   - PM2 will auto-restart
   - Docker has restart policy
   - System services auto-recover

## Monitoring

### PM2 Dashboard
```bash
pm2 monit              # Terminal dashboard
pm2 web                # Web dashboard on port 9615
pm2 describe mock-api-tunnel  # Detailed info
```

### Docker Logs
```bash
# Follow logs
docker logs -f munbon-mock-tunnel

# Last 100 lines
docker logs --tail 100 munbon-mock-api
```

### Health Checks
```bash
# Local mock server
curl http://localhost:4010/health

# Through tunnel (if DNS configured)
curl https://mock-api.yourdomain.com/health
```

## Best Practices

1. **Use PM2 or Docker** for automatic recovery
2. **Set up monitoring** to detect issues early
3. **Configure DNS** for a stable, memorable URL
4. **Enable logs** for troubleshooting
5. **Regular backups** of tunnel credentials

## Quick Reference

```bash
# Start everything (PM2)
pm2 start ~/.cloudflared/mock-tunnel-pm2.json

# Stop everything (PM2)
pm2 stop all

# Restart tunnel only
pm2 restart mock-api-tunnel

# View real-time logs
pm2 logs mock-api-tunnel --lines 100

# Check tunnel metrics
curl http://localhost:2000/metrics
```

The permanent tunnel eliminates all the stability issues you've experienced with temporary tunnels!