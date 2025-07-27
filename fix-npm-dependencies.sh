#!/bin/bash

echo "=== Fixing NPM Dependencies for All Services ==="

# Services that need package-lock.json
services=(
  "weather-monitoring"
  "water-level-monitoring"
  "rid-ms"
  "moisture-monitoring"
)

for service in "${services[@]}"; do
  echo ""
  echo "Processing $service..."
  
  if [ -d "services/$service" ]; then
    cd "services/$service"
    
    # Backup package.json
    cp package.json package.json.backup
    
    # Temporarily remove @munbon/shared if present
    if grep -q "@munbon/shared" package.json; then
      echo "Removing @munbon/shared dependency temporarily"
      grep -v "@munbon/shared" package.json > package.json.tmp && mv package.json.tmp package.json
    fi
    
    # Generate package-lock.json
    echo "Generating package-lock.json..."
    npm install
    
    # Restore original package.json
    mv package.json.backup package.json
    
    echo "✓ Fixed $service"
    cd ../..
  else
    echo "✗ Directory services/$service not found"
  fi
done

echo ""
echo "=== Checking Results ==="
for service in "${services[@]}"; do
  if [ -f "services/$service/package-lock.json" ]; then
    echo "✓ $service has package-lock.json"
  else
    echo "✗ $service missing package-lock.json"
  fi
done

echo ""
echo "Done! Now commit the package-lock.json files:"
echo "git add services/*/package-lock.json"
echo "git commit -m 'fix: Add missing package-lock.json files'"