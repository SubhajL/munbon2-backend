#!/bin/bash

# Render.com Keep-Alive Solutions
set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}======================================"
echo "Render.com Wake-Up Solutions"
echo "======================================"
echo -e "${NC}"

# Get Render URL
RENDER_URL="${RENDER_URL:-https://munbon-unified-api.onrender.com}"
echo -e "${YELLOW}Using Render URL: $RENDER_URL${NC}"

# Solution 1: Create a cron job pinger
echo -e "\n${GREEN}Solution 1: Creating Cron Job Pinger${NC}"
cat > render-pinger.sh << EOF
#!/bin/bash
# Ping Render service every 10 minutes to keep it alive
while true; do
    curl -s $RENDER_URL/health > /dev/null 2>&1
    echo "\$(date): Pinged $RENDER_URL"
    sleep 600  # 10 minutes
done
EOF
chmod +x render-pinger.sh

# Solution 2: Create GitHub Action
echo -e "\n${GREEN}Solution 2: Creating GitHub Action${NC}"
mkdir -p .github/workflows
cat > .github/workflows/keep-render-alive.yml << 'EOF'
name: Keep Render Service Alive

on:
  schedule:
    # Run every 10 minutes
    - cron: '*/10 * * * *'
  workflow_dispatch:  # Allow manual trigger

jobs:
  ping:
    runs-on: ubuntu-latest
    steps:
      - name: Ping Render Service
        run: |
          curl -s ${{ secrets.RENDER_URL }}/health || true
          echo "Pinged at $(date)"
        env:
          RENDER_URL: ${{ secrets.RENDER_URL }}
EOF

# Solution 3: AWS Lambda Warmer
echo -e "\n${GREEN}Solution 3: Creating AWS Lambda Warmer${NC}"
cat > lambda-warmer.js << 'EOF'
// AWS Lambda function to keep Render service warm
const https = require('https');

exports.handler = async (event) => {
    const url = process.env.RENDER_URL || 'https://munbon-unified-api.onrender.com';
    
    return new Promise((resolve, reject) => {
        https.get(`${url}/health`, (resp) => {
            let data = '';
            resp.on('data', (chunk) => { data += chunk; });
            resp.on('end', () => {
                console.log(`Warmed ${url} at ${new Date().toISOString()}`);
                resolve({
                    statusCode: 200,
                    body: JSON.stringify({ message: 'Service warmed', timestamp: new Date().toISOString() })
                });
            });
        }).on('error', (err) => {
            console.error('Error:', err.message);
            resolve({
                statusCode: 200,
                body: JSON.stringify({ error: err.message })
            });
        });
    });
};
EOF

# Solution 4: UptimeRobot Configuration
echo -e "\n${GREEN}Solution 4: UptimeRobot Configuration${NC}"
cat > uptimerobot-config.md << EOF
# UptimeRobot Configuration (FREE)

1. Go to https://uptimerobot.com and sign up (free)
2. Add New Monitor:
   - Monitor Type: HTTP(s)
   - Friendly Name: Munbon API
   - URL: $RENDER_URL/health
   - Monitoring Interval: 5 minutes
3. Save and activate

UptimeRobot will ping your service every 5 minutes, keeping it awake!
EOF

# Solution 5: Better Cron Service
echo -e "\n${GREEN}Solution 5: Cron-job.org Configuration${NC}"
cat > cronjob-config.md << EOF
# Cron-job.org Configuration (FREE)

1. Go to https://cron-job.org and sign up (free)
2. Create New Cron Job:
   - Title: Keep Munbon API Alive
   - URL: $RENDER_URL/health
   - Schedule: Every 5 minutes
   - Method: GET
3. Save and enable

This service will ping your API every 5 minutes for free!
EOF

# Solution 6: Cloudflare Worker
echo -e "\n${GREEN}Solution 6: Creating Cloudflare Worker${NC}"
cat > cloudflare-worker.js << 'EOF'
// Cloudflare Worker to keep Render service warm
addEventListener('scheduled', event => {
    event.waitUntil(keepWarm())
})

addEventListener('fetch', event => {
    event.respondWith(handleRequest(event.request))
})

async function keepWarm() {
    const response = await fetch('https://munbon-unified-api.onrender.com/health')
    console.log(`Service warmed at ${new Date().toISOString()}: ${response.status}`)
}

async function handleRequest(request) {
    await keepWarm()
    return new Response('Service warmed!', { status: 200 })
}
EOF

cat > wrangler.toml << 'EOF'
name = "render-warmer"
type = "javascript"

[triggers]
crons = ["*/10 * * * *"]  # Every 10 minutes

[env.production]
vars = { RENDER_URL = "https://munbon-unified-api.onrender.com" }
EOF

# Solution 7: In-app self-pinger
echo -e "\n${GREEN}Solution 7: Creating In-App Self-Pinger${NC}"
cat > src/self-pinger.js << 'EOF'
// Add this to your unified-api-render.js file

// Self-ping to prevent sleep (for Render.com)
if (process.env.NODE_ENV === 'production' && process.env.RENDER) {
    const selfPing = () => {
        const hostname = process.env.RENDER_EXTERNAL_HOSTNAME;
        if (hostname) {
            require('https').get(`https://${hostname}/health`, (res) => {
                console.log(`Self-ping: ${res.statusCode}`);
            }).on('error', (err) => {
                console.error('Self-ping error:', err.message);
            });
        }
    };
    
    // Ping every 10 minutes
    setInterval(selfPing, 10 * 60 * 1000);
    
    // Initial ping after 1 minute
    setTimeout(selfPing, 60 * 1000);
}
EOF

# Solution 8: Smart wake-up endpoint
echo -e "\n${GREEN}Solution 8: Creating Smart Wake-Up Endpoint${NC}"
cat > src/wake-up-endpoint.js << 'EOF'
// Add this endpoint to your API

app.get('/wake-up', async (req, res) => {
    const startTime = Date.now();
    
    // Perform a simple database query to warm up connections
    try {
        await timescaleDB.query('SELECT 1');
        const responseTime = Date.now() - startTime;
        
        res.json({
            status: 'awake',
            responseTime: `${responseTime}ms`,
            timestamp: new Date().toISOString(),
            message: responseTime > 1000 ? 'Service was sleeping, now awake!' : 'Service is already awake'
        });
    } catch (error) {
        res.status(500).json({
            status: 'error',
            message: error.message
        });
    }
});
EOF

# Create deployment script for Lambda warmer
cat > deploy-lambda-warmer.sh << 'EOF'
#!/bin/bash

echo "Deploying Lambda Warmer function..."

# Create deployment package
zip -j lambda-warmer.zip lambda-warmer.js

# Create Lambda function
aws lambda create-function \
    --function-name render-warmer \
    --runtime nodejs18.x \
    --role arn:aws:iam::YOUR_ACCOUNT_ID:role/lambda-execution-role \
    --handler lambda-warmer.handler \
    --zip-file fileb://lambda-warmer.zip \
    --timeout 30 \
    --memory-size 128 \
    --environment Variables={RENDER_URL=https://munbon-unified-api.onrender.com} \
    --region ap-southeast-1

# Create EventBridge rule to trigger every 5 minutes
aws events put-rule \
    --name render-warmer-schedule \
    --schedule-expression "rate(5 minutes)" \
    --region ap-southeast-1

# Add Lambda permission
aws lambda add-permission \
    --function-name render-warmer \
    --statement-id render-warmer-schedule \
    --action lambda:InvokeFunction \
    --principal events.amazonaws.com \
    --source-arn arn:aws:events:ap-southeast-1:YOUR_ACCOUNT_ID:rule/render-warmer-schedule \
    --region ap-southeast-1

# Connect rule to Lambda
aws events put-targets \
    --rule render-warmer-schedule \
    --targets "Id"="1","Arn"="arn:aws:lambda:ap-southeast-1:YOUR_ACCOUNT_ID:function:render-warmer" \
    --region ap-southeast-1

echo "Lambda warmer deployed!"
EOF

chmod +x deploy-lambda-warmer.sh

# Create comparison guide
cat > RENDER_WAKE_UP_GUIDE.md << 'EOF'
# Render.com Wake-Up Solutions Guide

## The Problem
Render's free tier puts services to sleep after 15 minutes of inactivity. First request after sleep takes 30-60 seconds (cold start).

## 🏆 Best Solutions Ranked

### 1. **UptimeRobot** (Easiest & Free) ⭐⭐⭐⭐⭐
- Sign up at uptimerobot.com
- Add monitor for your health endpoint
- Pings every 5 minutes
- **Pros**: Free, reliable, includes monitoring
- **Cons**: 5-minute interval limit on free tier

### 2. **Cron-job.org** (Simple & Free) ⭐⭐⭐⭐
- Sign up at cron-job.org
- Create cron job for health endpoint
- Can set custom intervals
- **Pros**: Free, flexible scheduling
- **Cons**: Basic features only

### 3. **GitHub Actions** (Integrated) ⭐⭐⭐⭐
- Uses your existing GitHub repo
- Runs on schedule
- **Pros**: No external service, version controlled
- **Cons**: Uses GitHub Actions minutes

### 4. **AWS Lambda** (Professional) ⭐⭐⭐⭐
- Serverless function to ping service
- Can integrate with your existing AWS setup
- **Pros**: Reliable, scalable, cheap
- **Cons**: Requires AWS account

### 5. **Cloudflare Workers** (Advanced) ⭐⭐⭐
- Edge-based pinging
- Global coverage
- **Pros**: Fast, reliable
- **Cons**: More complex setup

## 🚀 Quick Start (UptimeRobot)

1. Go to https://uptimerobot.com
2. Sign up (free)
3. Click "Add New Monitor"
4. Enter:
   - Monitor Type: HTTP(s)
   - URL: https://munbon-unified-api.onrender.com/health
   - Monitoring Interval: 5 minutes
5. Save!

Your service will stay awake 24/7!

## 💡 Pro Tips

1. **Combine Methods**: Use UptimeRobot + GitHub Actions for redundancy
2. **Monitor Multiple Endpoints**: Ping both /health and /wake-up
3. **Set Alerts**: Get notified if service is actually down
4. **Use Wake-Up Endpoint**: Warms up database connections too

## 📊 Cost Comparison

| Solution | Cost | Reliability | Setup Time |
|----------|------|-------------|------------|
| UptimeRobot | Free | High | 2 min |
| Cron-job.org | Free | Medium | 3 min |
| GitHub Actions | Free* | High | 5 min |
| AWS Lambda | ~$0.01/mo | Very High | 10 min |
| Cloudflare | Free* | Very High | 15 min |

*Within free tier limits

## 🔧 Implementation in Your API

Add this to your unified-api-render.js:

```javascript
// Wake-up endpoint with database warm-up
app.get('/wake-up', async (req, res) => {
    const start = Date.now();
    try {
        await timescaleDB.query('SELECT 1');
        res.json({
            status: 'awake',
            responseTime: Date.now() - start,
            timestamp: new Date().toISOString()
        });
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});
```

## 🎯 Recommended Setup

For production use:
1. **Primary**: UptimeRobot (5-min pings)
2. **Backup**: GitHub Actions (10-min pings)
3. **Monitoring**: UptimeRobot alerts
4. **Endpoint**: Use /wake-up for better warming

This ensures 99.9% uptime on Render's free tier!
EOF

echo -e "\n${GREEN}======================================"
echo "Render Wake-Up Solutions Created!"
echo "======================================"
echo -e "${NC}"
echo "Solutions available:"
echo "1. UptimeRobot (Recommended) - See uptimerobot-config.md"
echo "2. Cron-job.org - See cronjob-config.md"
echo "3. GitHub Actions - .github/workflows/keep-render-alive.yml"
echo "4. AWS Lambda - Run ./deploy-lambda-warmer.sh"
echo "5. Local Pinger - Run ./render-pinger.sh"
echo ""
echo -e "${YELLOW}Quick Start:${NC}"
echo "1. Sign up at https://uptimerobot.com (free)"
echo "2. Add monitor for: $RENDER_URL/health"
echo "3. Your API stays awake 24/7!"
echo -e "${GREEN}======================================${NC}"