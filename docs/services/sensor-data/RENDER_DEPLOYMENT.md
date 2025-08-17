# Render.com Deployment Instructions

## Quick Start

1. **Sign up** at https://render.com (free, no credit card required)

2. **Connect GitHub**:
   - Go to Dashboard → New → Web Service
   - Connect your GitHub account
   - Select your repository

3. **Configure Service**:
   - **Name**: munbon-unified-api
   - **Runtime**: Node
   - **Build Command**: `npm install --production`
   - **Start Command**: `node src/unified-api-render.js`

4. **Environment Variables** (auto-filled from render.yaml):
   - All variables will be set automatically
   - Database will be created automatically

5. **Deploy**:
   - Click "Create Web Service"
   - Wait for deployment (5-10 minutes)

## Manual CLI Deployment

```bash
# Install Render CLI (optional)
brew tap render-oss/render
brew install render

# Deploy
render up
```

## Get Your API URL

After deployment, your API will be available at:
```
https://munbon-unified-api.onrender.com
```

## Update AWS Lambda

Run this command with your Render URL:
```bash
aws lambda update-function-configuration \
    --function-name munbon-sensor-handler \
    --environment "Variables={UNIFIED_API_URL=https://munbon-unified-api.onrender.com,INTERNAL_API_KEY=munbon-internal-f3b89263126548}" \
    --region ap-southeast-1
```

## Notes

- Free tier services sleep after 15 minutes of inactivity
- First request after sleep takes ~30 seconds (cold start)
- For always-on service, upgrade to paid plan ($7/month)
