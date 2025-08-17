# Munbon Public API - Vercel Deployment

## Why Vercel?

### Advantages over AWS Lambda:
1. **Simpler deployment** - Just `vercel` command
2. **Automatic HTTPS** - No API Gateway setup
3. **Free custom domains** - munbon-api.vercel.app
4. **Better free tier** - 100k requests/month
5. **Faster cold starts** - Edge runtime
6. **Built-in monitoring** - No CloudWatch setup

## Quick Start

### 1. Install Vercel CLI
```bash
npm install -g vercel
```

### 2. Deploy
```bash
cd vercel-deployment
vercel

# Follow prompts:
# - Login/signup (free)
# - Project name: munbon-public-api
# - Deploy
```

### 3. Your API is Live!
```
https://munbon-public-api.vercel.app/api/v1/public/water-levels/latest
```

## API Endpoints

All endpoints require `X-API-Key` header.

### Water Level
- GET `/api/v1/public/water-levels/latest`
- GET `/api/v1/public/water-levels/timeseries?date=30/06/2568`
- GET `/api/v1/public/water-levels/statistics?date=30/06/2568`

### Moisture
- GET `/api/v1/public/moisture/latest`
- GET `/api/v1/public/moisture/timeseries?date=30/06/2568`
- GET `/api/v1/public/moisture/statistics?date=30/06/2568`

### AOS/Weather
- GET `/api/v1/public/aos/latest`
- GET `/api/v1/public/aos/timeseries?date=30/06/2568`
- GET `/api/v1/public/aos/statistics?date=30/06/2568`

## Environment Variables

Set in Vercel Dashboard (Settings → Environment Variables):

```bash
# API Keys for authentication
VALID_API_KEYS=rid-ms-prod-key1,rid-ms-dev-key2,test-key-123

# Your local API (via tunnel)
INTERNAL_API_URL=https://your-tunnel.ngrok.io
INTERNAL_KEY=your-internal-api-key
```

## Local Development

```bash
# Install dependencies
npm install

# Run locally
npm run dev

# Test
curl -H "X-API-Key: test-key-123" http://localhost:3000/api/water-levels/latest
```

## Production Setup

### 1. Connect to Local Databases

Use Cloudflare Tunnel (free) or ngrok:

```bash
# Cloudflare Tunnel
cloudflared tunnel create munbon-api
cloudflared tunnel run munbon-api

# Or ngrok
ngrok http 3000
```

### 2. Update Environment Variables

In Vercel Dashboard:
- `INTERNAL_API_URL`: Your tunnel URL
- `VALID_API_KEYS`: Production API keys

### 3. Custom Domain (Optional)

In Vercel Dashboard → Domains:
- Add `api.munbon-irrigation.com`
- Vercel handles SSL automatically

## Cost

**FREE** for:
- 100,000 requests/month
- 100 GB-hours compute
- Unlimited deployments
- Custom domains
- SSL certificates

## Monitoring

Built-in analytics at:
https://vercel.com/dashboard/[your-project]/analytics

## Comparison with AWS

| Feature | AWS Lambda | Vercel |
|---------|------------|---------|
| Setup Time | 2-3 hours | 10 minutes |
| Monthly Cost | ~$5-10 | FREE |
| Deployment | Complex | `vercel` |
| Monitoring | CloudWatch | Built-in |
| Custom Domain | Extra work | Included |