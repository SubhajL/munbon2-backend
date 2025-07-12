#!/bin/bash

# Update Lambda to use the new tunnel URL
NEW_TUNNEL_URL="${1:-https://violet-pears-lose.loca.lt}"

echo "Updating Lambda functions to use: $NEW_TUNNEL_URL"

STAGE="prod"
SERVICE="munbon-data-api"

# Function list
functions=(
    "${SERVICE}-${STAGE}-waterLevelLatest"
    "${SERVICE}-${STAGE}-waterLevelTimeseries"
    "${SERVICE}-${STAGE}-waterLevelStatistics"
    "${SERVICE}-${STAGE}-moistureLatest"
    "${SERVICE}-${STAGE}-moistureTimeseries"
    "${SERVICE}-${STAGE}-moistureStatistics"
    "${SERVICE}-${STAGE}-aosLatest"
    "${SERVICE}-${STAGE}-aosTimeseries"
    "${SERVICE}-${STAGE}-aosStatistics"
    "${SERVICE}-${STAGE}-corsOptions"
)

for func in "${functions[@]}"; do
    echo "Updating $func..."
    aws lambda update-function-configuration \
        --function-name "$func" \
        --environment Variables="{
            TUNNEL_URL='$NEW_TUNNEL_URL',
            INTERNAL_API_KEY='munbon-internal-f3b89263126548',
            EXTERNAL_API_KEYS='rid-ms-prod-key1,tmd-weather-key2,university-key3',
            STAGE='$STAGE'
        }" \
        --region ap-southeast-1 > /dev/null 2>&1
    
    if [ $? -eq 0 ]; then
        echo "✅ Updated $func"
    else
        echo "❌ Failed to update $func"
    fi
done

echo ""
echo "Test with:"
echo "curl -H \"X-API-Key: rid-ms-prod-key1\" https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public/water-levels/latest"