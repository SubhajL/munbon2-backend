#!/bin/bash

# Script to build all Docker images for local development
# Optimized for MacBook M4 Pro (ARM64)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
REGISTRY="${REGISTRY:-localhost:5000}"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

print_status() {
    echo -e "${GREEN}[BUILD]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Enable BuildKit for better performance
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1

# Check if local registry is running
check_registry() {
    if ! curl -s http://localhost:5000/v2/ > /dev/null; then
        print_warning "Local registry not running. Starting it..."
        docker run -d -p 5000:5000 --restart=always --name registry registry:2 || true
    fi
}

# Build a service
build_service() {
    local service_path=$1
    local service_name=$2
    local dockerfile=${3:-Dockerfile}
    
    if [ -d "$service_path" ]; then
        print_status "Building $service_name..."
        
        cd "$service_path"
        
        # Build for production
        docker build \
            --platform linux/arm64 \
            --target production \
            -t "$REGISTRY/$service_name:latest" \
            -t "$REGISTRY/$service_name:$(date +%Y%m%d-%H%M%S)" \
            -f "$dockerfile" \
            .
        
        # Build development image
        docker build \
            --platform linux/arm64 \
            --target development \
            -t "$REGISTRY/$service_name:dev" \
            -f "$dockerfile" \
            .
        
        # Push to local registry
        docker push "$REGISTRY/$service_name:latest"
        docker push "$REGISTRY/$service_name:dev"
        
        print_status "$service_name built and pushed successfully"
    else
        print_warning "Service directory not found: $service_path"
    fi
}

# Main execution
main() {
    print_status "Starting Docker build process..."
    
    # Check registry
    check_registry
    
    # Build infrastructure services
    print_status "Building infrastructure services..."
    build_service "$PROJECT_ROOT/services/infrastructure/api-gateway" "munbon/api-gateway"
    build_service "$PROJECT_ROOT/services/infrastructure/auth-service" "munbon/auth-service"
    build_service "$PROJECT_ROOT/services/infrastructure/config-service" "munbon/config-service"
    
    # Build core services
    print_status "Building core services..."
    build_service "$PROJECT_ROOT/services/core/sensor-data-service" "munbon/sensor-data-service"
    build_service "$PROJECT_ROOT/services/core/gis-service" "munbon/gis-service"
    build_service "$PROJECT_ROOT/services/core/water-control-service" "munbon/water-control-service"
    
    # Build AI/ML services (if they exist)
    if [ -d "$PROJECT_ROOT/services/ai-ml" ]; then
        print_status "Building AI/ML services..."
        build_service "$PROJECT_ROOT/services/ai-ml/prediction-service" "munbon/prediction-service"
    fi
    
    print_status "Build process completed!"
    print_status "Images available at: $REGISTRY"
    
    # Show built images
    echo
    print_status "Built images:"
    docker images | grep "$REGISTRY/munbon" | head -20
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --service)
            # Build specific service
            SERVICE_NAME="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [--service SERVICE_NAME]"
            echo "  --service: Build only specified service"
            exit 0
            ;;
        *)
            print_error "Unknown argument: $1"
            exit 1
            ;;
    esac
done

# Run main or build specific service
if [ -n "$SERVICE_NAME" ]; then
    build_service "$PROJECT_ROOT/services/$SERVICE_NAME" "munbon/$(basename $SERVICE_NAME)"
else
    main
fi