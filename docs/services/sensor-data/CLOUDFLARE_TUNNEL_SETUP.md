# Cloudflare Tunnel Setup for Munbon API

This guide shows how to set up Cloudflare Tunnel to provide TLS 1.0+ support for your API endpoints.

## Quick Start (30 seconds)

### Option 1: One Command
```bash
cd services/sensor-data
./quick-tunnel.sh
```

### Option 2: Docker
```bash
cd services/sensor-data
docker-compose -f docker-compose.tunnel.yml up
```

### Option 3: Direct Command
```bash
cloudflared tunnel --url https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com
```

## What You Get

After running any of the above commands, you'll get:
- ✅ **Free subdomain** like `https://gentle-flower-1234.trycloudflare.com`
- ✅ **TLS 1.0, 1.1, 1.2, 1.3 support**
- ✅ **Old cipher suite compatibility**
- ✅ **Same API functionality**
- ✅ **No domain purchase needed**

## API Endpoints

Your original endpoint:
```
https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/{token}/telemetry
```

Becomes:
```
https://your-tunnel-subdomain.trycloudflare.com/dev/api/v1/{token}/telemetry
```

## Testing TLS Support

### Test TLS 1.0
```bash
curl --tlsv1.0 -X GET https://your-tunnel.trycloudflare.com/dev/api/v1/munbon-m2m-moisture/attributes
```

### Test TLS 1.1
```bash
curl --tlsv1.1 -X GET https://your-tunnel.trycloudflare.com/dev/api/v1/munbon-m2m-moisture/attributes
```

### Test with specific cipher
```bash
curl --ciphers 'AES256-SHA' -X GET https://your-tunnel.trycloudflare.com/dev/api/v1/munbon-m2m-moisture/attributes
```

## Setup Options

### 1. Interactive Setup
```bash
./setup-cloudflare-tunnel.sh
```
Choose option 1 for quick temporary tunnel.

### 2. Docker Compose
```bash
# Start tunnel
docker-compose -f docker-compose.tunnel.yml up -d

# Check logs for URL
docker logs munbon-cloudflare-tunnel

# Stop tunnel
docker-compose -f docker-compose.tunnel.yml down
```

### 3. Manual Installation
```bash
# macOS
brew install cloudflare/cloudflare/cloudflared

# Linux (Debian/Ubuntu)
wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared-linux-amd64.deb

# Run tunnel
cloudflared tunnel --url https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com
```

## Permanent Tunnel Setup

For a permanent subdomain (requires free Cloudflare account):

1. Run setup script and choose option 2:
```bash
./setup-cloudflare-tunnel.sh
```

2. Follow the prompts to:
   - Login to Cloudflare
   - Create permanent tunnel
   - Configure DNS (if you have a domain)

## TLS/Cipher Support

Cloudflare Tunnel automatically supports:
- **SSL/TLS Versions**: SSL 3.0*, TLS 1.0, TLS 1.1, TLS 1.2, TLS 1.3
- **Cipher Suites**: Including the requested legacy ciphers:
  - TLS_RSA_WITH_AES_256_CBC_SHA
  - TLS_RSA_WITH_AES_128_CBC_SHA
  - TLS_RSA_WITH_RC4_128_SHA
  - TLS_RSA_WITH_RC4_128_MD5
  - TLS_RSA_WITH_3DES_EDE_CBC_SHA
  - TLS_RSA_WITH_AES_256_CBC_SHA256

*Note: SSL 3.0 support depends on Cloudflare's current security policy

## Monitoring

Check tunnel status:
```bash
# If installed locally
cloudflared tunnel list

# If using Docker
docker ps | grep cloudflare-tunnel
docker logs munbon-cloudflare-tunnel
```

## Troubleshooting

### Tunnel URL not showing
```bash
# Check logs
docker logs munbon-cloudflare-tunnel 2>&1 | grep trycloudflare

# Or check saved URL
cat tunnel-url.txt
```

### Connection issues
```bash
# Test direct API first
curl https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/munbon-m2m-moisture/attributes

# Then test tunnel
curl https://your-tunnel.trycloudflare.com/dev/api/v1/munbon-m2m-moisture/attributes
```

### Port already in use
The tunnel doesn't use local ports, so this shouldn't be an issue.

## Security Notes

1. **Temporary tunnels** change URL on restart
2. **No authentication** is added by the tunnel - your API keys still work the same
3. **Traffic is encrypted** end-to-end
4. **DDoS protection** included by Cloudflare

## Cost

- **Quick tunnel**: FREE forever
- **Permanent tunnel**: FREE with Cloudflare account
- **No bandwidth limits** for reasonable use
- **No credit card required**

## Next Steps

1. Run the quick tunnel to test
2. Share the tunnel URL with devices needing old TLS support
3. Keep the original API endpoint for modern devices
4. Consider permanent tunnel for production use