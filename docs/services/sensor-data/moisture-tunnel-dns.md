# DNS Configuration for Moisture Tunnel

## Required DNS Records

Add the following CNAME records to your DNS provider for beautifyai.io:

### 1. Main moisture endpoint
```
Type: CNAME
Name: munbon-moisture
Target: 01a272d3-abf2-4c58-9a03-f2d08072adf0.cfargotunnel.com
TTL: Auto or 300
```

### 2. Health check endpoint
```
Type: CNAME
Name: munbon-moisture-health
Target: 01a272d3-abf2-4c58-9a03-f2d08072adf0.cfargotunnel.com
TTL: Auto or 300
```

## Cloudflare Dashboard Setup

1. Log into Cloudflare Dashboard: https://dash.cloudflare.com
2. Select the beautifyai.io domain
3. Go to DNS → Records
4. Add the CNAME records above

## Testing DNS

After adding records, test with:
```bash
# Check DNS propagation
nslookup munbon-moisture.beautifyai.io
dig munbon-moisture.beautifyai.io CNAME

# Test the endpoint (after tunnel is running)
curl https://munbon-moisture.beautifyai.io/health
```

## Tunnel URLs

- Public URL: https://munbon-moisture.beautifyai.io
- Tunnel URL: https://01a272d3-abf2-4c58-9a03-f2d08072adf0.cfargotunnel.com
- Health Check: https://munbon-moisture-health.beautifyai.io/health
