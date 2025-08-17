# Data Ingestion: AWS vs Vercel Comparison

## Architecture Comparison

### AWS Architecture
```
Sensors → API Gateway → Lambda → SQS → Local Consumer → TimescaleDB
         ($3.50/M req)  ($0.20/M) ($0.40/M)
```

### Vercel Architecture
```
Sensors → Vercel Functions → Queue/Direct → TimescaleDB
         (FREE up to 100k/mo)
```

## 📊 Detailed Comparison

| Feature | AWS Lambda + SQS | Vercel Functions |
|---------|------------------|-------------------|
| **Free Tier** | 1M requests/month | 100k requests/month |
| **Setup Time** | 2-3 hours | 15 minutes |
| **Queue Options** | SQS ($0.40/M msgs) | Upstash Kafka (10k/day free) |
| **File Storage** | S3 (5GB free) | Vercel Blob (1GB free) |
| **Deployment** | Complex (Serverless) | Simple (`vercel`) |
| **Cold Start** | 1-2 seconds | 200-500ms |
| **Max Timeout** | 15 minutes | 10 seconds (Edge), 5 min (Node) |
| **Max Payload** | 6MB (sync) | 4.5MB |
| **Monitoring** | CloudWatch | Built-in analytics |

## 💰 Cost Analysis (Monthly)

### Low Volume (< 100k requests)
- **AWS**: ~$5-10 (API Gateway minimum)
- **Vercel**: $0 (FREE)

### Medium Volume (500k requests)
- **AWS**: ~$25-30
- **Vercel**: $20 (Pro plan)

### High Volume (2M requests)
- **AWS**: ~$50-70
- **Vercel**: $20 (Pro plan)

## 🎯 Queue Options for Vercel

### 1. Direct Write (Recommended for < 1k req/hour)
```typescript
// No queue, direct database write
Sensor → Vercel → Your API → Database
```

### 2. Upstash Kafka (Free: 10k messages/day)
```typescript
// Reliable message queue
Sensor → Vercel → Upstash Kafka → Consumer → Database
```

### 3. Upstash Redis (Free: 10k commands/day)
```typescript
// Simple queue with Redis
Sensor → Vercel → Redis Queue → Consumer → Database
```

### 4. Vercel KV (Free: 3k requests/day)
```typescript
// Built-in key-value storage
Sensor → Vercel → Vercel KV → Cron Job → Database
```

## ✅ Advantages of Vercel for Ingestion

1. **Simpler Architecture**: No API Gateway, SQS setup
2. **Lower Cost**: Free for development/low volume
3. **Faster Deployment**: Minutes vs hours
4. **Better DX**: Modern tooling, TypeScript native
5. **Global Edge**: Automatic global distribution

## ⚠️ Limitations of Vercel

1. **Timeout Limits**: 10 seconds (Edge), 5 minutes (Node.js)
2. **No Native Queue**: Need external service (Upstash)
3. **Storage Limits**: 1GB Blob storage on free tier
4. **Request Limits**: 100k/month on free tier

## 🏗️ Implementation Examples

### 1. Simple Direct Write (No Queue)
```typescript
// Best for: < 1000 requests/hour
export default async function handler(req, res) {
  const data = req.body;
  
  // Direct write to your database API
  await fetch('https://your-api.com/ingest', {
    method: 'POST',
    body: JSON.stringify(data)
  });
  
  return res.json({ success: true });
}
```

### 2. With Upstash Kafka Queue
```typescript
// Best for: High volume, reliability needed
import { Kafka } from '@upstash/kafka';

const kafka = new Kafka({
  url: process.env.KAFKA_URL,
  username: process.env.KAFKA_USERNAME,
  password: process.env.KAFKA_PASSWORD,
});

export default async function handler(req, res) {
  await kafka.producer().produce('sensor-data', req.body);
  return res.json({ success: true });
}
```

### 3. Hybrid Approach
```typescript
// Best for: Mixed volume
export default async function handler(req, res) {
  const { urgency } = req.body;
  
  if (urgency === 'high') {
    // Direct write for urgent data
    await writeDirectly(req.body);
  } else {
    // Queue for batch processing
    await queueForLater(req.body);
  }
  
  return res.json({ success: true });
}
```

## 📝 Migration Path from AWS to Vercel

### Phase 1: Dual Ingestion (1-2 weeks)
```
Sensors → Both AWS and Vercel
        → Monitor and compare
```

### Phase 2: Gradual Migration (2-4 weeks)
```
10% → Vercel
90% → AWS
(Increase gradually)
```

### Phase 3: Full Migration
```
100% → Vercel
AWS → Decommission
```

## 🎯 Recommendation

### Use Vercel for Ingestion if:
- ✅ Volume < 100k requests/month
- ✅ Want simpler architecture
- ✅ Need faster deployment
- ✅ Cost sensitive
- ✅ OK with 10-second timeout

### Stay with AWS if:
- ❌ Need > 5 minute processing
- ❌ Require native SQS features
- ❌ Already have complex AWS setup
- ❌ Need 15+ minute Lambda timeout

## 🚀 Quick Start

```bash
# Deploy ingestion to Vercel
cd vercel-deployment
vercel

# Test ingestion endpoint
curl -X POST https://your-app.vercel.app/api/ingest/munbon-ridr-water-level/telemetry \
  -H "Content-Type: application/json" \
  -d '{"deviceId": "wl001", "level": 12.5}'
```

## 💡 Best Practice Architecture

For Munbon project, I recommend:

```
1. Sensor Data (High frequency):
   Sensors → Vercel → Upstash Kafka → Local Consumer → TimescaleDB

2. SHAPE Files (Low frequency):
   Upload → Vercel → Vercel Blob → Webhook → Local Processor → PostGIS

3. Public API:
   Users → Vercel Edge → Cache → Local API → Databases
```

This gives you:
- **$0/month** for development
- **~$20/month** for production
- **Simple architecture**
- **Fast deployment**
- **Global distribution**