# Kubernetes Infrastructure Setup

This directory contains Kubernetes configurations for the Munbon Irrigation Backend microservices.

## Local Development Setup

### Prerequisites

1. **Docker Desktop** (recommended) or **Colima**
2. **kubectl** - Kubernetes CLI
3. **Helm** - Kubernetes package manager
4. **Kustomize** - Kubernetes configuration management

### Quick Start

#### Option 1: Docker Desktop (Recommended for M4 Pro)
```bash
# Enable Kubernetes in Docker Desktop
# Docker Desktop → Settings → Kubernetes → Enable Kubernetes

# Verify installation
kubectl version
kubectl cluster-info

# Apply base configurations
kubectl apply -k overlays/local
```

#### Option 2: Colima (Lightweight Alternative)
```bash
# Install and start Colima
brew install colima
colima start --kubernetes --cpu 4 --memory 8 --disk 60

# Verify installation
kubectl version
kubectl cluster-info
```

### Directory Structure

```
kubernetes/
├── base/                    # Base configurations
│   ├── namespaces/         # Namespace definitions
│   ├── rbac/              # RBAC configurations
│   ├── network-policies/   # Network isolation rules
│   └── storage/           # Storage classes
├── overlays/              # Environment-specific configs
│   ├── local/            # Local development
│   ├── staging/          # Staging environment
│   └── production/       # Production environment
└── charts/               # Helm charts
    └── munbon/          # Main application chart
```

## Resource Allocation for M4 Pro

Recommended Docker Desktop settings:
- CPUs: 6 cores (50% of M4 Pro)
- Memory: 12 GB
- Disk: 80 GB
- Enable Kubernetes: ✓

## Development Workflow

1. **Start local cluster**
   ```bash
   # If using Docker Desktop, just ensure Kubernetes is enabled
   # If using Colima:
   colima start --kubernetes
   ```

2. **Deploy infrastructure**
   ```bash
   make deploy-local
   ```

3. **Access services**
   ```bash
   # API Gateway
   kubectl port-forward -n munbon svc/api-gateway 3000:3000
   
   # Monitoring
   kubectl port-forward -n monitoring svc/grafana 3001:3000
   ```

4. **Monitor cluster**
   ```bash
   # Use k9s for interactive monitoring
   k9s
   
   # Or use Lens
   open -a Lens
   ```

## Security Notes

- Local development uses simplified RBAC
- Self-signed certificates for HTTPS
- No network policies by default (can be enabled)
- Secrets stored in Kubernetes (not external KMS)