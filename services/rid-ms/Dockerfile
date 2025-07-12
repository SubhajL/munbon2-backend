FROM node:20-alpine AS builder

# Install build dependencies for native modules
RUN apk add --no-cache python3 make g++ gdal-dev proj-dev

WORKDIR /app

# Copy package files
COPY package*.json ./
RUN npm ci --only=production

# Copy source code
COPY . .

# Build TypeScript
RUN npm run build

# Production stage
FROM node:20-alpine

# Install runtime dependencies for GDAL/PROJ
RUN apk add --no-cache gdal proj

WORKDIR /app

# Copy node_modules and built files from builder
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/package*.json ./

# Create directories for file processing
RUN mkdir -p /tmp/rid-ms/uploads /tmp/rid-ms/processed /tmp/rid-ms/archive && \
    chown -R node:node /tmp/rid-ms

# Create log directory
RUN mkdir -p /var/log/rid-ms && chown -R node:node /var/log/rid-ms

USER node

EXPOSE 3048

CMD ["node", "dist/index.js"]