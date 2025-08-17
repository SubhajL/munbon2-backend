# Step-by-Step: Adding CNAME Records in Cloudflare

## Getting the Tunnel ID First

Before adding DNS records, you need to get your tunnel ID:

```bash
# Run this to see your tunnel ID
cloudflared tunnel list

# Or check the output from setup script
cat ~/.cloudflared/config-moisture.yml
```

Your tunnel ID will look like: `f3b89263-1265-4843-b08c-5391e73e8c75`

## Adding CNAME Records in Cloudflare Dashboard

### Step 1: Click "Add record" Button
You're already in the right place. Click the blue "Add record" button.

### Step 2: Add First CNAME (munbon-moisture)

Fill in these fields:

1. **Type**: Select `CNAME` from dropdown
2. **Name**: Enter `munbon-moisture`
3. **Target**: Enter `[YOUR-TUNNEL-ID].cfargotunnel.com`
   - Example: `f3b89263-1265-4843-b08c-5391e73e8c75.cfargotunnel.com`
4. **Proxy status**: Toggle ON (orange cloud) ✓
5. **TTL**: Leave as "Auto"

Click **Save**

### Step 3: Add Second CNAME (munbon-moisture-health)

Click "Add record" again and fill in:

1. **Type**: Select `CNAME`
2. **Name**: Enter `munbon-moisture-health`
3. **Target**: Enter the same `[YOUR-TUNNEL-ID].cfargotunnel.com`
4. **Proxy status**: Toggle ON (orange cloud) ✓
5. **TTL**: Leave as "Auto"

Click **Save**

## Visual Guide

```
┌─────────────────────────────────────────────────────┐
│ Add DNS Record                                      │
├─────────────────────────────────────────────────────┤
│ Type:    [CNAME ▼]                                 │
│                                                     │
│ Name:    [munbon-moisture                    ]     │
│          (required)                                 │
│                                                     │
│ Target:  [xxxxx-xxxx-xxxx.cfargotunnel.com ]      │
│          (required)                                 │
│                                                     │
│ Proxy status:  [ ☁️ Proxied ✓ ]                    │
│                                                     │
│ TTL:     [Auto ▼]                                  │
│                                                     │
│ Comment: [Moisture sensor tunnel endpoint    ]     │
│          (optional)                                 │
│                                                     │
│ [Cancel]                              [Save]        │
└─────────────────────────────────────────────────────┘
```

## Important Notes

1. **Proxy Status**: Make sure the cloud icon is ORANGE (Proxied). This enables Cloudflare's features including:
   - SSL/TLS termination
   - DDoS protection
   - Legacy cipher support

2. **Name Field**: Only enter the subdomain part:
   - ✅ Correct: `munbon-moisture`
   - ❌ Wrong: `munbon-moisture.beautifyai.io`

3. **Target Field**: Must include `.cfargotunnel.com`:
   - ✅ Correct: `f3b89263-1265-4843-b08c-5391e73e8c75.cfargotunnel.com`
   - ❌ Wrong: `f3b89263-1265-4843-b08c-5391e73e8c75`

## After Adding Records

### Verify DNS Records

After saving both records, you should see them in your DNS list:

```
Type    Name                    Content                                     Proxy   TTL
CNAME   munbon-moisture        xxxxx-xxxx-xxxx.cfargotunnel.com          Proxied  Auto
CNAME   munbon-moisture-health xxxxx-xxxx-xxxx.cfargotunnel.com          Proxied  Auto
```

### Test DNS Resolution (wait 2-5 minutes)

```bash
# Test DNS resolution
dig munbon-moisture.beautifyai.io CNAME +short

# Should return something like:
# xxxxx-xxxx-xxxx.cfargotunnel.com.
```

### Test the Endpoints

```bash
# Test health endpoint (after tunnel is running)
curl https://munbon-moisture-health.beautifyai.io/health

# Test with legacy TLS
curl --tlsv1.0 https://munbon-moisture.beautifyai.io/health
```

## Troubleshooting

### If DNS doesn't resolve:
1. Wait 5-10 minutes for propagation
2. Check if records show "Proxied" status
3. Try clearing DNS cache: `sudo dscacheutil -flushcache`

### If you get SSL errors:
1. Make sure Proxy is ON (orange cloud)
2. Check SSL/TLS settings in Cloudflare (should be "Full" or "Flexible")
3. Ensure tunnel is running: `pm2 status munbon-moisture-tunnel`

### If you can't find your tunnel ID:
```bash
# List all tunnels
cloudflared tunnel list

# If no tunnels exist, create one first:
cd /Users/subhajlimanond/dev/munbon2-backend/services/sensor-data
./setup-moisture-tunnel.sh
```