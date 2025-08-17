# ngrok Setup (Alternative to Cloudflare)

## 1. Install ngrok
```bash
brew install ngrok
# Or download from: https://ngrok.com/download
```

## 2. Sign up for free account
- Go to https://ngrok.com/signup
- Get your auth token

## 3. Authenticate
```bash
ngrok authtoken YOUR_AUTH_TOKEN
```

## 4. Run tunnel
```bash
ngrok http 3000
```

Free tier limitations:
- Random URL each time (unless you pay)
- 40 connections/minute
- 1 online tunnel

For production, use Cloudflare Tunnel instead.
