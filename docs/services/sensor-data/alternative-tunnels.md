# Alternative Tunneling Solutions

## 1. ngrok (More Stable)
```bash
# Install
brew install ngrok

# Authenticate (free account)
ngrok authtoken YOUR_TOKEN

# Run with custom subdomain (paid feature)
ngrok http 3000 --subdomain=munbon-api

# Or use free random URL
ngrok http 3000
```

## 2. Tailscale (P2P VPN)
```bash
# Install
brew install tailscale

# Connect
tailscale up

# Access via stable hostname
# http://your-machine-name.tailnet-name.ts.net:3000
```

## 3. LocalTunnel (Free Alternative)
```bash
npm install -g localtunnel

# Run with custom subdomain
lt --port 3000 --subdomain munbon-api
```

## 4. Serveo (SSH-based)
```bash
# No installation needed
ssh -R 80:localhost:3000 serveo.net
```