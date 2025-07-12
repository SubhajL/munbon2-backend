# Oracle Cloud + AWS Integration Architecture

## Current Setup vs Oracle Setup

### Current (Unstable)
```
[Local Machine] → [Cloudflare Tunnel] → [AWS Lambda] → [API Gateway]
  Unified API      (Changes URLs)         Proxy          Public API
```

### With Oracle Cloud (Stable)
```
[Oracle Cloud VM] ←→ [AWS Services]
  - Unified API        - Lambda (via HTTPS)
  - Fixed Public IP    - SQS (send messages)
  - Always Online      - API Gateway (receive calls)
  - No Tunnel Needed   - Parameter Store (config)
```

## Connection Patterns

### 1. Lambda → Oracle (Most Common)
```
API Gateway → Lambda → Oracle Unified API
                ↓
         HTTP GET/POST to
     http://oracle-ip:3000/api/v1/...
```

### 2. Oracle → SQS (For Async Processing)
```
Oracle Unified API → AWS SQS → Lambda Consumer
   sensor data        queue     process data
```

### 3. Oracle → Lambda Direct (Less Common)
```
Oracle Unified API → Lambda Function
                     Direct invocation
                     via AWS SDK
```

## Benefits

1. **No More Tunnel Issues**
   - Fixed IP address
   - No "context canceled" errors
   - No URL changes

2. **Better Performance**
   - Direct HTTP connection
   - Lower latency
   - No tunnel overhead

3. **Cost Effective**
   - Oracle: Free forever (ARM VM)
   - AWS: Only pay for Lambda/SQS usage
   - No tunnel service costs

4. **High Availability**
   - Oracle VM: 99.95% SLA
   - Can setup multiple VMs for redundancy
   - Load balancing possible

## Setup Steps

1. **Deploy to Oracle Cloud**
   ```bash
   # Create ARM VM (Always Free)
   # Install Node.js and unified API
   # Configure firewall
   ```

2. **Update AWS Lambda**
   ```javascript
   // Change from:
   const TUNNEL_URL = await getParameterStore('/munbon/tunnel-url');
   
   // To:
   const API_ENDPOINT = await getParameterStore('/munbon/oracle-api-endpoint');
   ```

3. **Configure Security**
   - Oracle: Open port 3000
   - Use API keys for authentication
   - Optional: Add SSL certificate

4. **Test Connection**
   ```bash
   # From Lambda or locally
   curl http://oracle-public-ip:3000/health \
     -H "X-Internal-Key: your-key"
   ```

## Monitoring

1. **Oracle Side**
   - PM2 for process management
   - CloudWatch Agent (optional)
   - Custom health checks

2. **AWS Side**
   - Lambda logs
   - API Gateway metrics
   - SQS queue monitoring

## Failover Strategy

1. **Primary**: Oracle Cloud VM 1
2. **Secondary**: Oracle Cloud VM 2 (different region)
3. **Fallback**: AWS EC2 t2.micro (if needed)