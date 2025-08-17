# Free Hosting Options for TLS Proxy

## Always Free Cloud Providers

### 1. Oracle Cloud (Best Free Tier)
- **2 AMD VMs** with 1GB RAM each - ALWAYS FREE
- **Perfect for nginx/HAProxy**
- Setup: https://www.oracle.com/cloud/free/

### 2. Google Cloud Platform
- **e2-micro instance** - Always free
- **30GB disk, 1GB transfer/month**
- Location: us-central1, us-west1, or us-east1

### 3. AWS EC2
- **t2.micro** - 750 hours/month (1 year)
- After 1 year, use t4g.micro with free trial

### 4. Azure
- **B1s instance** - 750 hours/month (1 year)
- 1 vCPU, 1GB RAM

## Serverless Options (Forever Free)

### 1. Cloudflare Workers
```javascript
// Cloudflare Worker script
export default {
  async fetch(request) {
    const url = new URL(request.url);
    url.hostname = 'c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com';
    
    return fetch(url, {
      method: request.method,
      headers: request.headers,
      body: request.body
    });
  }
};
```
- **100,000 requests/day free**
- Supports custom TLS

### 2. Deno Deploy
```typescript
// Deno Deploy script
import { serve } from "https://deno.land/std/http/server.ts";

serve(async (req) => {
  const url = new URL(req.url);
  const apiUrl = `https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com${url.pathname}${url.search}`;
  
  return await fetch(apiUrl, {
    method: req.method,
    headers: req.headers,
    body: req.body,
  });
});
```

## Quick Comparison

| Solution | Forever Free | TLS Control | Setup Time |
|----------|--------------|-------------|------------|
| Cloudflare (Domain) | ✅ | Full | 30 mins |
| Cloudflare Workers | ✅ | Limited | 10 mins |
| Oracle Cloud + nginx | ✅ | Full | 1 hour |
| GCP + nginx | ✅ | Full | 1 hour |
| AWS EC2 | 1 year only | Full | 45 mins |

## Recommended: Cloudflare Free Tier
1. No server to maintain
2. Global CDN included
3. Full TLS/cipher control
4. DDoS protection
5. Zero cost forever