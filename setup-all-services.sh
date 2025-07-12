#!/bin/bash

# Munbon Backend Services Setup Script
# This script sets up Kong API Gateway, Authentication Service, and GIS Service

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to wait for service
wait_for_service() {
    local host=$1
    local port=$2
    local service=$3
    local max_attempts=30
    local attempt=1

    print_status "Waiting for $service to be ready..."
    
    while ! nc -z "$host" "$port" >/dev/null 2>&1; do
        if [ $attempt -eq $max_attempts ]; then
            print_error "$service failed to start on $host:$port"
            return 1
        fi
        echo -n "."
        sleep 2
        ((attempt++))
    done
    
    echo ""
    print_success "$service is ready!"
    return 0
}

# Function to generate secure random string
generate_secret() {
    openssl rand -base64 32 | tr -d "=+/" | cut -c1-32
}

# Check prerequisites
print_status "Checking prerequisites..."

if ! command_exists docker; then
    print_error "Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command_exists docker-compose; then
    print_error "Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

if ! command_exists node; then
    print_error "Node.js is not installed. Please install Node.js 18+ first."
    exit 1
fi

if ! command_exists npm; then
    print_error "npm is not installed. Please install npm first."
    exit 1
fi

print_success "All prerequisites are installed!"

# Set working directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Generate JWT secret if not exists
if [ ! -f ".env.jwt.secret" ]; then
    print_status "Generating JWT secret..."
    JWT_SECRET=$(generate_secret)
    echo "JWT_SECRET=$JWT_SECRET" > .env.jwt.secret
    print_success "JWT secret generated and saved to .env.jwt.secret"
else
    print_status "Using existing JWT secret from .env.jwt.secret"
    source .env.jwt.secret
fi

# Step 1: Start Infrastructure Services
print_status "Starting infrastructure services..."

# Start Kong and its dependencies
print_status "Starting Kong API Gateway..."
docker-compose -f docker-compose.kong.yml up -d

# Start GIS PostgreSQL and Redis
print_status "Starting GIS database and cache services..."
docker-compose -f services/gis/docker-compose.dev.yml up -d

# Wait for databases to be ready
wait_for_service localhost 5432 "Kong PostgreSQL"
wait_for_service localhost 5433 "Kong PostgreSQL (Kong DB)"
wait_for_service localhost 6379 "Redis"

# Additional wait for PostgreSQL initialization
print_status "Waiting for database initialization..."
sleep 10

# Step 2: Configure Kong
print_status "Configuring Kong API Gateway..."
cd infrastructure/kong

if [ -f "setup-kong.sh" ]; then
    chmod +x setup-kong.sh
    ./setup-kong.sh
else
    print_warning "Kong setup script not found, applying configuration manually..."
    
    # Wait for Kong to be ready
    wait_for_service localhost 8001 "Kong Admin API"
    
    # Apply Kong configuration
    curl -X POST http://localhost:8001/config \
        -F config=@kong.yml \
        2>/dev/null || print_warning "Kong configuration might already be applied"
fi

cd "$SCRIPT_DIR"
print_success "Kong API Gateway configured!"

# Step 3: Setup Authentication Service
print_status "Setting up Authentication Service..."
cd services/auth

# Create .env file if not exists
if [ ! -f ".env" ]; then
    print_status "Creating .env file for Auth Service..."
    cp .env.example .env
    
    # Update .env with generated JWT secret
    if [ "$(uname)" == "Darwin" ]; then
        # macOS
        sed -i '' "s/JWT_SECRET=.*/JWT_SECRET=$JWT_SECRET/" .env
    else
        # Linux
        sed -i "s/JWT_SECRET=.*/JWT_SECRET=$JWT_SECRET/" .env
    fi
    
    print_warning "Please update the .env file with your SMTP and OAuth credentials!"
fi

# Install dependencies
print_status "Installing Auth Service dependencies..."
npm install

# Create database if not exists
print_status "Creating auth database..."
docker exec -i munbon-kong-db psql -U postgres -tc "SELECT 1 FROM pg_database WHERE datname = 'munbon_auth'" | grep -q 1 || \
docker exec -i munbon-kong-db psql -U postgres -c "CREATE DATABASE munbon_auth"

# Run migrations
print_status "Running Auth Service migrations..."
npm run typeorm migration:run || print_warning "Migrations might already be applied"

cd "$SCRIPT_DIR"
print_success "Authentication Service setup complete!"

# Step 4: Setup GIS Service
print_status "Setting up GIS Service..."
cd services/gis

# Create .env file if not exists
if [ ! -f ".env" ]; then
    print_status "Creating .env file for GIS Service..."
    cp .env.example .env
    
    # Update .env with generated JWT secret
    if [ "$(uname)" == "Darwin" ]; then
        # macOS
        sed -i '' "s/JWT_SECRET=.*/JWT_SECRET=$JWT_SECRET/" .env
    else
        # Linux
        sed -i "s/JWT_SECRET=.*/JWT_SECRET=$JWT_SECRET/" .env
    fi
fi

# Install dependencies
print_status "Installing GIS Service dependencies..."
npm install

# The database is already initialized with PostGIS via docker-compose init script

cd "$SCRIPT_DIR"
print_success "GIS Service setup complete!"

# Step 5: Create start scripts
print_status "Creating service start scripts..."

# Create start script for all services
cat > start-services.sh << 'EOF'
#!/bin/bash

echo "Starting Munbon Backend Services..."

# Start Auth Service
echo "Starting Authentication Service..."
cd services/auth
npm run dev &
AUTH_PID=$!
cd ../..

# Start GIS Service
echo "Starting GIS Service..."
cd services/gis
npm run dev &
GIS_PID=$!
cd ../..

echo "Services started with PIDs:"
echo "  Auth Service: $AUTH_PID"
echo "  GIS Service: $GIS_PID"

# Wait for services
wait $AUTH_PID $GIS_PID
EOF

chmod +x start-services.sh

# Create stop script
cat > stop-services.sh << 'EOF'
#!/bin/bash

echo "Stopping Munbon Backend Services..."

# Stop Node.js services
pkill -f "node.*services/auth" || true
pkill -f "node.*services/gis" || true

# Stop Docker services
docker-compose -f docker-compose.kong.yml down
docker-compose -f services/gis/docker-compose.dev.yml down

echo "All services stopped!"
EOF

chmod +x stop-services.sh

# Create health check script
cat > check-health.sh << 'EOF'
#!/bin/bash

echo "Checking service health..."

# Function to check endpoint
check_endpoint() {
    local name=$1
    local url=$2
    
    if curl -s -f "$url" > /dev/null; then
        echo "✓ $name is healthy"
    else
        echo "✗ $name is not responding"
    fi
}

# Check services
check_endpoint "Kong Proxy" "http://localhost:8000"
check_endpoint "Kong Admin" "http://localhost:8001/status"
check_endpoint "Auth Service" "http://localhost:3001/health"
check_endpoint "GIS Service" "http://localhost:3006/health"
check_endpoint "Auth via Kong" "http://localhost:8000/auth/health"
check_endpoint "GIS via Kong" "http://localhost:8000/gis/health"

# Check databases
echo ""
echo "Checking databases..."
docker exec munbon-kong-db pg_isready -U postgres > /dev/null && echo "✓ Kong PostgreSQL is ready" || echo "✗ Kong PostgreSQL is not ready"
docker exec munbon-gis-postgres pg_isready -U postgres > /dev/null && echo "✓ GIS PostgreSQL is ready" || echo "✗ GIS PostgreSQL is not ready"
docker exec munbon-gis-redis redis-cli ping > /dev/null && echo "✓ Redis is ready" || echo "✗ Redis is not ready"
EOF

chmod +x check-health.sh

# Create test script
cat > test-integration.sh << 'EOF'
#!/bin/bash

echo "Running integration tests..."

# Test Kong health
echo "1. Testing Kong health..."
curl -s http://localhost:8000 | jq . || echo "Kong root endpoint failed"

# Test Auth Service
echo -e "\n2. Testing Auth Service login..."
LOGIN_RESPONSE=$(curl -s -X POST http://localhost:8000/auth/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@munbon.com", "password": "Admin123!"}')

if [ -z "$LOGIN_RESPONSE" ]; then
    echo "Login failed - no response"
else
    echo "$LOGIN_RESPONSE" | jq .
    TOKEN=$(echo "$LOGIN_RESPONSE" | jq -r '.data.accessToken // empty')
    
    if [ -n "$TOKEN" ]; then
        echo -e "\n3. Testing GIS Service with authentication..."
        curl -s http://localhost:8000/gis/api/v1/zones \
          -H "Authorization: Bearer $TOKEN" | jq .
    else
        echo "No token received, skipping authenticated requests"
    fi
fi

echo -e "\nIntegration tests complete!"
EOF

chmod +x test-integration.sh

print_success "Setup scripts created!"

# Step 6: Final instructions
echo ""
echo "========================================"
echo "       SETUP COMPLETE! 🎉"
echo "========================================"
echo ""
print_success "All services have been configured!"
echo ""
echo "IMPORTANT NEXT STEPS:"
echo ""
echo "1. Update environment files with your specific configurations:"
echo "   - services/auth/.env (SMTP, OAuth credentials)"
echo "   - services/gis/.env (if needed)"
echo ""
echo "2. Start all services:"
echo "   ./start-services.sh"
echo ""
echo "3. Check service health:"
echo "   ./check-health.sh"
echo ""
echo "4. Run integration tests:"
echo "   ./test-integration.sh"
echo ""
echo "5. Stop all services:"
echo "   ./stop-services.sh"
echo ""
echo "Service URLs:"
echo "  - Kong Proxy: http://localhost:8000"
echo "  - Kong Admin: http://localhost:8001"
echo "  - Kong Manager: http://localhost:8002"
echo "  - Auth Service: http://localhost:3001"
echo "  - GIS Service: http://localhost:3006"
echo ""
echo "Your JWT secret has been saved to: .env.jwt.secret"
echo "Keep this file secure and use the same secret across all services!"
echo ""
print_warning "Remember to create an admin user for the Auth Service!"
echo ""