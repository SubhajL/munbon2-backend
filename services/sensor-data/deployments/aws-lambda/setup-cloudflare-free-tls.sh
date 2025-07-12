#!/bin/bash

# Setup Cloudflare Free Tier with Custom TLS Support

echo "=== Cloudflare Free TLS Setup ==="
echo ""
echo "Cloudflare Free Tier supports:"
echo "✅ SSL 3.0, TLS 1.0, 1.1, 1.2, 1.3"
echo "✅ Custom cipher suites"
echo "✅ Free SSL certificate"
echo "✅ No monthly charges"
echo ""

# Step-by-step guide
cat << 'EOF'
SETUP STEPS:

1. Sign up for Cloudflare Free account:
   https://dash.cloudflare.com/sign-up

2. Add your domain (or get a free subdomain from Freenom)

3. Point Cloudflare to your API Gateway:
   - Add DNS record:
     Type: CNAME
     Name: api (or your subdomain)
     Target: c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com
     Proxy: ON (orange cloud)

4. Configure SSL/TLS settings:
   - Go to SSL/TLS → Edge Certificates
   - Minimum TLS Version: TLS 1.0 (or even SSL 3.0 if needed)
   - Enable "Legacy Browser Support"

5. Set cipher suites via API:
   curl -X PATCH "https://api.cloudflare.com/client/v4/zones/YOUR_ZONE_ID/settings/ciphers" \
     -H "X-Auth-Email: your-email@example.com" \
     -H "X-Auth-Key: your-api-key" \
     -H "Content-Type: application/json" \
     --data '{
       "value": [
         "TLS_RSA_WITH_AES_256_CBC_SHA",
         "TLS_RSA_WITH_AES_128_CBC_SHA",
         "TLS_RSA_WITH_RC4_128_SHA",
         "TLS_RSA_WITH_RC4_128_MD5",
         "TLS_RSA_WITH_3DES_EDE_CBC_SHA",
         "TLS_RSA_WITH_AES_256_CBC_SHA256"
       ]
     }'

6. Your new endpoint:
   https://api.yourdomain.com/dev/api/v1/munbon-m2m-moisture/telemetry
   (Cloudflare handles TLS → forwards to API Gateway)

BENEFITS:
- Zero cost
- Global CDN included
- DDoS protection
- Supports very old TLS/SSL versions
- Custom cipher configuration
EOF

echo ""
echo "Alternative: Use Cloudflare Tunnel (also free):"
echo "cloudflared tunnel --url https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com"