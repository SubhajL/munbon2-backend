#!/bin/bash

# Setup script for local Kubernetes development
# Optimized for MacBook M4 Pro

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_section() {
    echo -e "\n${BLUE}=== $1 ===${NC}\n"
}

# Check prerequisites
check_prerequisites() {
    print_section "Checking Prerequisites"
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker Desktop."
        exit 1
    fi
    print_status "Docker: $(docker --version)"
    
    # Check kubectl
    if ! command -v kubectl &> /dev/null; then
        print_warning "kubectl not found. Installing..."
        brew install kubectl
    fi
    print_status "kubectl: $(kubectl version --client --short 2>/dev/null || echo 'installed')"
    
    # Check Helm
    if ! command -v helm &> /dev/null; then
        print_warning "Helm not found. Installing..."
        brew install helm
    fi
    print_status "Helm: $(helm version --short)"
    
    # Check if Kubernetes is enabled in Docker Desktop
    if kubectl cluster-info &> /dev/null; then
        print_status "Kubernetes is running"
    else
        print_error "Kubernetes is not running. Please enable Kubernetes in Docker Desktop settings."
        print_warning "Docker Desktop → Settings → Kubernetes → Enable Kubernetes"
        exit 1
    fi
}

# Setup local registry
setup_local_registry() {
    print_section "Setting up Local Docker Registry"
    
    if docker ps | grep -q registry:2; then
        print_status "Local registry is already running"
    else
        print_status "Starting local Docker registry..."
        docker run -d -p 5000:5000 --restart=always --name registry registry:2
        print_status "Local registry started at localhost:5000"
    fi
}

# Install local-path-provisioner for dynamic volume provisioning
install_local_path_provisioner() {
    print_section "Installing Local Path Provisioner"
    
    if kubectl get storageclass local-path &> /dev/null; then
        print_status "Local path provisioner already installed"
    else
        print_status "Installing local-path-provisioner..."
        kubectl apply -f https://raw.githubusercontent.com/rancher/local-path-provisioner/v0.0.24/deploy/local-path-storage.yaml
        print_status "Local path provisioner installed"
    fi
}

# Apply base Kubernetes configurations
apply_base_configs() {
    print_section "Applying Base Kubernetes Configurations"
    
    cd "$PROJECT_ROOT/infrastructure/kubernetes"
    
    print_status "Creating namespaces..."
    kubectl apply -k base/namespaces
    
    print_status "Setting up RBAC..."
    kubectl apply -k base/rbac
    
    print_status "Creating storage classes..."
    kubectl apply -k base/storage
    
    print_status "Base configurations applied successfully"
}

# Apply local overlay
apply_local_overlay() {
    print_section "Applying Local Development Overlay"
    
    cd "$PROJECT_ROOT/infrastructure/kubernetes"
    
    print_status "Applying local development configurations..."
    kubectl apply -k overlays/local
    
    print_status "Local overlay applied successfully"
}

# Install Helm dependencies
install_helm_deps() {
    print_section "Installing Helm Dependencies"
    
    print_status "Adding Helm repositories..."
    helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
    helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
    helm repo add grafana https://grafana.github.io/helm-charts
    helm repo update
    
    print_status "Helm repositories updated"
}

# Deploy nginx-ingress for local development
deploy_ingress() {
    print_section "Deploying NGINX Ingress Controller"
    
    if helm list -n munbon-infrastructure | grep -q nginx-ingress; then
        print_status "NGINX Ingress already deployed"
    else
        print_status "Installing NGINX Ingress..."
        helm install nginx-ingress ingress-nginx/ingress-nginx \
            --namespace munbon-infrastructure \
            --set controller.service.type=NodePort \
            --set controller.service.nodePorts.http=30080 \
            --set controller.service.nodePorts.https=30443 \
            --set controller.resources.requests.cpu=100m \
            --set controller.resources.requests.memory=128Mi
        
        print_status "NGINX Ingress deployed"
        print_status "HTTP available at: http://localhost:30080"
        print_status "HTTPS available at: https://localhost:30443"
    fi
}

# Install monitoring stack (optional)
install_monitoring() {
    print_section "Monitoring Stack (Optional)"
    
    read -p "Do you want to install Prometheus and Grafana? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_status "Installing Prometheus..."
        helm install prometheus prometheus-community/prometheus \
            --namespace munbon-monitoring \
            --set server.persistentVolume.enabled=false \
            --set alertmanager.enabled=false \
            --set pushgateway.enabled=false
        
        print_status "Installing Grafana..."
        helm install grafana grafana/grafana \
            --namespace munbon-monitoring \
            --set persistence.enabled=false \
            --set adminPassword=admin
        
        print_status "Monitoring stack installed"
        print_status "Access Grafana: kubectl port-forward -n munbon-monitoring svc/grafana 3001:80"
    else
        print_status "Skipping monitoring stack installation"
    fi
}

# Create helpful aliases
create_aliases() {
    print_section "Creating Helpful Aliases"
    
    cat > "$PROJECT_ROOT/.k8s-aliases" << 'EOF'
# Munbon Kubernetes Aliases
alias k='kubectl'
alias kn='kubectl -n munbon'
alias kni='kubectl -n munbon-infrastructure'
alias knm='kubectl -n munbon-monitoring'
alias knd='kubectl -n munbon-data'
alias kna='kubectl -n munbon-ai'

# Port forwarding shortcuts
alias munbon-api='kubectl port-forward -n munbon svc/api-gateway 3000:3000'
alias munbon-grafana='kubectl port-forward -n munbon-monitoring svc/grafana 3001:80'

# Logs shortcuts
alias munbon-logs='kubectl logs -n munbon -f'
alias munbon-logs-api='kubectl logs -n munbon -f -l app=api-gateway'

# Quick status
alias munbon-status='kubectl get pods -n munbon'
alias munbon-all='kubectl get all -n munbon'
EOF
    
    print_status "Aliases created in $PROJECT_ROOT/.k8s-aliases"
    print_warning "To use aliases, run: source $PROJECT_ROOT/.k8s-aliases"
}

# Print summary
print_summary() {
    print_section "Setup Complete!"
    
    echo "Kubernetes local development environment is ready."
    echo
    echo "Quick start commands:"
    echo "  kubectl get nodes                    # Check cluster status"
    echo "  kubectl get ns                       # List namespaces"
    echo "  kubectl get pods -A                  # List all pods"
    echo "  kubectl port-forward -n munbon svc/api-gateway 3000:3000  # Access API"
    echo
    echo "Local services:"
    echo "  Docker Registry: localhost:5000"
    echo "  Ingress HTTP:    http://localhost:30080"
    echo "  Ingress HTTPS:   https://localhost:30443"
    echo
    echo "Next steps:"
    echo "  1. Run docker-compose up to start databases"
    echo "  2. Build and push service images to localhost:5000"
    echo "  3. Deploy services using Helm or kubectl"
}

# Main execution
main() {
    print_section "Munbon Kubernetes Local Setup"
    echo "Setting up Kubernetes for MacBook M4 Pro..."
    
    check_prerequisites
    setup_local_registry
    install_local_path_provisioner
    apply_base_configs
    apply_local_overlay
    install_helm_deps
    deploy_ingress
    install_monitoring
    create_aliases
    print_summary
}

# Run main function
main "$@"