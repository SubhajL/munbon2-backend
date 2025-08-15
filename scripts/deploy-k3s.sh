#!/bin/bash
set -euo pipefail

# Deployment script for K3s cluster
# This script deploys services to the K3s cluster on EC2

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
K8S_DIR="$PROJECT_ROOT/k8s"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}=== Deploying to K3s Cluster ===${NC}"

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}kubectl is not installed. Please install kubectl first.${NC}"
    exit 1
fi

# Set kubeconfig
export KUBECONFIG="${KUBECONFIG:-$PROJECT_ROOT/k3s-kubeconfig.yaml}"

if [ ! -f "$KUBECONFIG" ]; then
    echo -e "${RED}Kubeconfig not found at $KUBECONFIG${NC}"
    echo "Please download it from the EC2 instance:"
    echo "scp ubuntu@43.209.22.250:/home/ubuntu/k3s-kubeconfig.yaml $PROJECT_ROOT/"
    exit 1
fi

# Test cluster connectivity
echo -e "${YELLOW}Testing cluster connectivity...${NC}"
if ! kubectl cluster-info &> /dev/null; then
    echo -e "${RED}Cannot connect to K3s cluster. Check your kubeconfig.${NC}"
    exit 1
fi

# Create namespace
echo -e "${YELLOW}Creating namespace...${NC}"
kubectl apply -f "$K8S_DIR/base/namespace.yaml"

# Apply configmap
echo -e "${YELLOW}Applying configuration...${NC}"
kubectl apply -f "$K8S_DIR/base/configmap.yaml"

# Deploy databases first
echo -e "${YELLOW}Deploying databases...${NC}"
kubectl apply -f "$K8S_DIR/services/redis.yaml"
kubectl apply -f "$K8S_DIR/services/postgres.yaml"

# Wait for databases to be ready
echo -e "${YELLOW}Waiting for databases to be ready...${NC}"
kubectl wait --for=condition=ready pod -l app=redis -n munbon --timeout=120s || true
kubectl wait --for=condition=ready pod -l app=postgres -n munbon --timeout=120s || true

# Deploy services
echo -e "${YELLOW}Deploying services...${NC}"
for service in "$K8S_DIR/services"/*-service.yaml; do
    if [ -f "$service" ]; then
        echo "Deploying $(basename "$service")..."
        kubectl apply -f "$service"
    fi
done

# Show deployment status
echo -e "${GREEN}=== Deployment Status ===${NC}"
kubectl get all -n munbon

echo -e "${GREEN}Deployment complete!${NC}"
echo -e "${YELLOW}To check logs:${NC} kubectl logs -n munbon <pod-name>"
echo -e "${YELLOW}To scale:${NC} kubectl scale deployment/<name> --replicas=3 -n munbon"
echo -e "${YELLOW}To update:${NC} kubectl set image deployment/<name> <container>=<new-image> -n munbon"