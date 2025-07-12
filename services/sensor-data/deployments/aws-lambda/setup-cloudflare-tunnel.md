# Cloudflare Tunnel Setup (Free)

## 1. Install Cloudflared
```bash
# macOS
brew install cloudflared

# Or download from: https://github.com/cloudflare/cloudflared/releases
```

## 2. Login to Cloudflare
```bash
cloudflared tunnel login
```

## 3. Create Tunnel
```bash
cloudflared tunnel create munbon-api
```

## 4. Create config file (~/.cloudflared/config.yml)
```yaml
tunnel: munbon-api
credentials-file: /Users/YOUR_USER/.cloudflared/TUNNEL_ID.json

ingress:
  - hostname: munbon-api.YOUR_DOMAIN.com
    service: http://localhost:3000
  - service: http_status:404
```

## 5. Route traffic
```bash
cloudflared tunnel route dns munbon-api munbon-api.YOUR_DOMAIN.com
```

## 6. Run tunnel
```bash
cloudflared tunnel run munbon-api
```

Your local API is now accessible at: https://munbon-api.YOUR_DOMAIN.com
