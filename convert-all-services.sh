#!/bin/bash

# Convert all remaining TypeScript services to JavaScript

SERVICES=(
    "weather-monitoring"
    "water-level-monitoring"
    "rid-ms"
    "moisture-monitoring"
    "awd-control"
)

echo "Converting all remaining TypeScript services to JavaScript..."
echo "Services to convert: ${SERVICES[@]}"
echo

for service in "${SERVICES[@]}"; do
    echo "========================================="
    echo "Converting $service..."
    echo "========================================="
    
    ./convert-ts-to-js-universal.sh "$service"
    
    if [ $? -eq 0 ]; then
        echo "✅ $service converted successfully"
    else
        echo "❌ $service conversion failed"
    fi
    echo
done

echo "========================================="
echo "Conversion Summary:"
echo "========================================="

for service in "${SERVICES[@]}"; do
    if [ -d "services/$service/src_typescript_backup" ]; then
        echo "✅ $service - Converted"
    else
        echo "❌ $service - Not converted"
    fi
done