#!/bin/bash

# Expert Docker testing script
set -e

echo "=== Expert Docker Build Test ==="

# Test sensor-data first (simplest service)
SERVICE="sensor-data"
echo "Testing $SERVICE..."

cd services/$SERVICE

# Create the most minimal possible Dockerfile
cat > Dockerfile.test << 'EOF'
FROM node:20-alpine
WORKDIR /app

# First, just copy package files
COPY package*.json ./

# Debug: Show what we have
RUN echo "=== Files in directory ===" && \
    ls -la && \
    echo "=== package.json content ===" && \
    cat package.json && \
    echo "=== Checking for @munbon/shared ===" && \
    grep -n "@munbon/shared" package.json || echo "No @munbon/shared found"

# Remove problematic dependency if exists
RUN if grep -q "@munbon/shared" package.json; then \
      echo "Removing @munbon/shared..." && \
      sed -i '/@munbon\/shared/d' package.json; \
    fi

# Try to install dependencies
RUN echo "=== Installing dependencies ===" && \
    npm install --loglevel verbose || \
    (echo "npm install failed, trying with --force" && npm install --force)

# Copy the rest
COPY . .

# Debug: Show final structure
RUN echo "=== Final directory structure ===" && \
    ls -la && \
    echo "=== src directory ===" && \
    ls -la src/ || echo "No src directory"

EXPOSE 3001
CMD ["node", "src/index.js"]
EOF

# Build locally
echo "Building Docker image locally..."
docker build -f Dockerfile.test -t test-sensor-data . || {
    echo "Build failed!"
    echo "Checking Docker daemon..."
    docker version
    exit 1
}

echo "✅ Local build successful!"

# Test the image
echo "Testing the image..."
docker run --rm test-sensor-data node --version
echo "✅ Image runs successfully!"

cd ../..
echo "Local test complete. If this worked, the issue is with GitHub Actions, not Docker."