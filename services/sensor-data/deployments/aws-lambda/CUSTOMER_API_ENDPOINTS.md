# Customer API Endpoints - All Options Available

## Important: Your Current API Remains Unchanged! ✅

Your existing AWS API Gateway endpoint continues to work exactly as before:
```
https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/{token}/telemetry
```

## What We're Adding (Not Replacing)

We're adding alternative endpoints for devices that need old TLS/cipher support:

### Option 1: Both Endpoints via Cloudflare
```javascript
// Modern devices (TLS 1.2+) can use either:
POST https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/munbon-m2m-moisture/telemetry
POST https://api.munbon.com/dev/api/v1/munbon-m2m-moisture/telemetry

// Old devices (TLS 1.0, SSL 3.0) must use:
POST https://api.munbon.com/dev/api/v1/munbon-m2m-moisture/telemetry
```

### Option 2: Direct + Proxy Endpoints
```javascript
// Direct to AWS (TLS 1.2 only):
POST https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/munbon-m2m-moisture/telemetry

// Via Proxy (supports old TLS):
POST https://proxy.munbon.com/dev/api/v1/munbon-m2m-moisture/telemetry
```

## Customer Communication Template

```
Dear Customer,

Your current API endpoint remains fully operational:
https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/...

For devices requiring legacy TLS support (SSL 3.0, TLS 1.0/1.1), we now offer:
https://api.munbon.com/dev/api/v1/...

Both endpoints:
- Use the same API tokens
- Accept the same request format
- Return the same responses
- Process data identically

No changes needed unless your device requires legacy TLS support.
```

## Technical Flow

```
┌─────────────────┐
│ Modern Devices  │──────► AWS API Gateway ──────► Lambda ──► SQS
└─────────────────┘              ▲
                                 │
┌─────────────────┐              │
│  Old Devices    │──► Proxy ────┘
└─────────────────┘   (Cloudflare/nginx)
                      with TLS 1.0/SSL 3.0
```

## API Compatibility Matrix

| Endpoint Type | URL | TLS Support | API Token | Request Format |
|--------------|-----|-------------|-----------|----------------|
| AWS Direct | c0zc2kfzd6.execute-api... | TLS 1.2+ | Same ✅ | Same ✅ |
| Cloudflare | api.munbon.com | SSL 3.0 - TLS 1.3 | Same ✅ | Same ✅ |
| nginx Proxy | proxy.munbon.com | SSL 3.0 - TLS 1.2 | Same ✅ | Same ✅ |

## Benefits of This Approach

1. **Zero Disruption**: Existing integrations continue working
2. **Gradual Migration**: Customers can switch when ready
3. **Device Compatibility**: Support both modern and legacy devices
4. **Same API Logic**: No code changes, just TLS handling
5. **Cost Efficient**: Only proxy traffic that needs old TLS

## Example Customer Scenarios

### Customer A - Modern Sensors
- Keep using: `https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com`
- No changes needed

### Customer B - Mixed Fleet
- Modern sensors: Use AWS endpoint (faster, direct)
- Old sensors: Use proxy endpoint (TLS 1.0 support)

### Customer C - Prefers Single Endpoint
- All devices use: `https://api.munbon.com` (works for all TLS versions)

## Implementation Priority

1. **Keep AWS endpoint running** (already done ✅)
2. **Add Cloudflare** for customers needing old TLS
3. **Monitor usage** to see if proxy is actually needed
4. **Communicate options** to customers clearly