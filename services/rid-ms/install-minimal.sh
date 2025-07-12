#!/bin/bash

echo "Installing minimal dependencies for Lambda deployment..."

# Only install what we actually need for the simple handler
npm install --save-dev @types/node
npm install --save-dev @types/aws-lambda

echo "Creating dist directory..."
mkdir -p dist/lambda

echo "Compiling simple handler..."
npx tsc src/lambda/simple-handler.ts \
  --outDir dist \
  --module commonjs \
  --target ES2018 \
  --esModuleInterop \
  --skipLibCheck \
  --resolveJsonModule \
  --lib ES2018,DOM

echo "Setup complete! You can now run: serverless deploy --config serverless-simple.yml"