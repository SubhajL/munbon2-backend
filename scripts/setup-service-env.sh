#!/bin/bash

# Script to set up environment files for a service
# Usage: ./setup-service-env.sh <service-name>

set -e

SERVICE=$1

if [ -z "$SERVICE" ]; then
    echo "Usage: $0 <service-name>"
    echo "Example: $0 auth"
    exit 1
fi

SERVICE_DIR="services/$SERVICE"

if [ ! -d "$SERVICE_DIR" ]; then
    echo "Error: Service directory $SERVICE_DIR does not exist"
    exit 1
fi

echo "Setting up environment for $SERVICE service..."

# Copy shared environment first
if [ -f ".env.shared" ]; then
    echo "# Imported from .env.shared" > "$SERVICE_DIR/.env.local"
    cat .env.shared >> "$SERVICE_DIR/.env.local"
    echo "" >> "$SERVICE_DIR/.env.local"
    echo "# Service-specific overrides" >> "$SERVICE_DIR/.env.local"
fi

# Copy service-specific template
if [ -f "$SERVICE_DIR/.env.local.example" ]; then
    echo "Copying service-specific environment template..."
    if [ -f "$SERVICE_DIR/.env.local" ]; then
        cat "$SERVICE_DIR/.env.local.example" >> "$SERVICE_DIR/.env.local"
    else
        cp "$SERVICE_DIR/.env.local.example" "$SERVICE_DIR/.env.local"
    fi
    echo "✓ Created $SERVICE_DIR/.env.local"
else
    echo "⚠ No .env.local.example found for $SERVICE"
fi

# Add to .gitignore if not already there
if ! grep -q "^.env.local$" "$SERVICE_DIR/.gitignore" 2>/dev/null; then
    echo ".env.local" >> "$SERVICE_DIR/.gitignore"
    echo "✓ Added .env.local to .gitignore"
fi

echo ""
echo "Environment setup complete!"
echo "Edit $SERVICE_DIR/.env.local to set your local values"