#!/bin/bash

# API Key Generation Script for Munbon External API
# This script generates secure API keys for different organizations and use cases

echo "=== Munbon External API Key Generator ==="
echo ""

# Function to generate secure random key
generate_key() {
    openssl rand -hex 16
}

# Create .env.api-keys file with generated keys
cat > .env.api-keys << EOF
# Generated API Keys for Munbon External API
# Generated on: $(date)
# 
# IMPORTANT: Keep these keys secure and share only with authorized organizations
# Format: ORGANIZATION_PURPOSE=key

# Royal Irrigation Department (RID-MS)
# Full access to all sensor types and zones
RID_MS_PRODUCTION=rid-ms-prod-$(generate_key)
RID_MS_DEVELOPMENT=rid-ms-dev-$(generate_key)
RID_MS_STAGING=rid-ms-stage-$(generate_key)

# Thai Meteorological Department (TMD)
# Access only to AOS/weather data
TMD_WEATHER_API=tmd-weather-$(generate_key)

# Agricultural Research Organizations
# Limited to moisture data for research
KASETSART_RESEARCH=ku-research-$(generate_key)
AGRICULTURAL_DEPT=agri-dept-$(generate_key)

# Mobile Applications
# For official Munbon mobile app
MUNBON_MOBILE_IOS=mobile-ios-$(generate_key)
MUNBON_MOBILE_ANDROID=mobile-android-$(generate_key)

# Web Dashboard
# For official Munbon web dashboard
MUNBON_DASHBOARD=dashboard-$(generate_key)

# Partner Organizations (Limited Access)
# Zone-specific access for local organizations
ZONE1_PARTNER=zone1-partner-$(generate_key)
ZONE2_PARTNER=zone2-partner-$(generate_key)

# Testing and Development
# Short-lived keys for testing
TEST_KEY_30DAYS=test-30d-$(generate_key)

# Backup/Emergency Keys
EMERGENCY_KEY_1=emergency-1-$(generate_key)
EMERGENCY_KEY_2=emergency-2-$(generate_key)

# Combined environment variable for simple auth
# (comma-separated list for basic implementation)
EXTERNAL_API_KEYS=\${RID_MS_PRODUCTION},\${RID_MS_DEVELOPMENT},\${TMD_WEATHER_API},\${MUNBON_MOBILE_IOS},\${MUNBON_MOBILE_ANDROID}

# Enhanced API key configuration (JSON format)
API_KEYS_CONFIG='[
  {
    "key": "'"\${RID_MS_PRODUCTION}"'",
    "name": "RID-MS Production",
    "organization": "Royal Irrigation Department",
    "allowedDataTypes": ["water_level", "moisture", "aos"],
    "rateLimit": { "requestsPerHour": 10000, "requestsPerMinute": 200 }
  },
  {
    "key": "'"\${TMD_WEATHER_API}"'",
    "name": "TMD Weather API",
    "organization": "Thai Meteorological Department",
    "allowedDataTypes": ["aos"],
    "rateLimit": { "requestsPerHour": 5000, "requestsPerMinute": 100 }
  },
  {
    "key": "'"\${KASETSART_RESEARCH}"'",
    "name": "Kasetsart Research",
    "organization": "Kasetsart University",
    "allowedDataTypes": ["moisture"],
    "allowedZones": ["Zone 1", "Zone 2"],
    "rateLimit": { "requestsPerHour": 1000, "requestsPerMinute": 50 }
  }
]'
EOF

# Create API key documentation
cat > API_KEYS_DOCUMENTATION.md << 'EOF'
# API Key Documentation

## Key Distribution

### For RID-MS (Royal Irrigation Department)
- **Production Key**: `RID_MS_PRODUCTION`
  - Full access to all data types
  - All zones
  - Rate limit: 10,000 req/hour
  
- **Development Key**: `RID_MS_DEVELOPMENT`
  - Full access to all data types
  - All zones
  - Rate limit: 5,000 req/hour

### For TMD (Thai Meteorological Department)
- **Weather API Key**: `TMD_WEATHER_API`
  - Access to AOS/weather data only
  - All zones
  - Rate limit: 5,000 req/hour

### For Research Organizations
- **Kasetsart University**: `KASETSART_RESEARCH`
  - Access to moisture data only
  - Limited to Zone 1 & 2
  - Rate limit: 1,000 req/hour
  - Valid until: December 31, 2025

### For Mobile Applications
- **iOS App**: `MUNBON_MOBILE_IOS`
- **Android App**: `MUNBON_MOBILE_ANDROID`
  - Access to water level and moisture data
  - All zones
  - Rate limit: 50,000 req/hour

## Usage Instructions

Include the API key in the request header:
```
X-API-Key: your-api-key-here
```

## Security Guidelines

1. **Never share keys publicly** (GitHub, forums, etc.)
2. **Rotate keys regularly** (every 6-12 months)
3. **Use different keys** for dev/staging/production
4. **Monitor usage** for anomalies
5. **Revoke compromised keys** immediately

## Key Rotation Schedule

- Production keys: Every 12 months
- Development keys: Every 6 months
- Test keys: Every 30 days
- Mobile app keys: With each major release

## Contact

For key issues or additional access:
- Email: api-support@munbon-irrigation.go.th
- Phone: +66 XX XXX XXXX
EOF

echo ""
echo "=== API Keys Generated Successfully ==="
echo ""
echo "Files created:"
echo "1. .env.api-keys - Contains all generated API keys"
echo "2. API_KEYS_DOCUMENTATION.md - Documentation for key distribution"
echo ""
echo "IMPORTANT SECURITY STEPS:"
echo "1. Add .env.api-keys to .gitignore"
echo "2. Store keys in a secure password manager"
echo "3. Share keys only through secure channels"
echo "4. Set up key rotation reminders"
echo ""
echo "To use these keys:"
echo "1. Copy relevant keys from .env.api-keys to your .env file"
echo "2. Restart the sensor-data service"
echo "3. Share specific keys with authorized organizations"