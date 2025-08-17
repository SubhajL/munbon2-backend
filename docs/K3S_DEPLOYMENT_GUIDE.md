# K3s Deployment Guide for Munbon Irrigation Backend

## Overview

This guide provides a complete deployment solution using K3s (lightweight Kubernetes) on a single EC2 instance, replacing the previous Docker Compose approach with a more scalable, production-ready infrastructure.

## Infrastructure Setup

### Current EC2 Instance
- **Type**: t3.large (2 vCPU, 8GB RAM)
- **IP**: 43.209.22.250
- **Region**: ap-southeast-1
- **OS**: Ubuntu 22.04 LTS
- **K3s**: v1.32.6+k3s1 (installed)

### Why K3s?
- Lightweight: Only 512MB RAM overhead
- Built-in: Load balancer, ingress controller
- Production-ready: Used by many enterprises
- Easy: Single binary, simple operations
- Cost-effective: Runs all services on one EC2

## Quick Start

### 1. Prerequisites
```bash
# Install kubectl locally (macOS)
brew install kubectl

# Download kubeconfig
scp ubuntu@43.209.22.250:/home/ubuntu/k3s-kubeconfig.yaml ./k3s-kubeconfig.yaml
export KUBECONFIG=./k3s-kubeconfig.yaml

# Verify connection
kubectl get nodes
```

### 2. Deploy Services
```bash
# Run deployment script
./scripts/deploy-k3s.sh

# Or deploy manually
kubectl apply -f k8s/base/namespace.yaml
kubectl apply -f k8s/base/configmap.yaml
kubectl apply -f k8s/services/
```

### 3. Check Status
```bash
# View all resources
kubectl get all -n munbon

# Check logs
kubectl logs -n munbon deployment/auth-service

# Scale services
kubectl scale deployment/auth-service --replicas=3 -n munbon
```

## Service Architecture

### Resource Allocation (Optimized for t3.large)

| Service | Replicas | CPU Request | Memory Request | Total |
|---------|----------|-------------|----------------|-------|
| PostgreSQL | 1 | 250m | 512Mi | Core DB |
| TimescaleDB | 1 | 200m | 512Mi | Time-series |
| MongoDB | 1 | 200m | 512Mi | Documents |
| Redis | 1 | 100m | 128Mi | Cache |
| InfluxDB | 1 | 200m | 512Mi | Metrics |
| Kafka | 1 | 300m | 512Mi | Messaging |
| Auth Service | 2 | 200m | 256Mi | Core |
| API Gateway | 2 | 200m | 256Mi | Core |
| Other Services | 1-2 | 100-200m | 128-256Mi | Various |

**Total**: ~1.8 CPU, ~6GB RAM (fits in t3.large with overhead)

## GitHub Actions Deployment

### Setup Secrets
1. Go to GitHub repo → Settings → Secrets
2. Add these secrets:
   - `DOCKER_USERNAME`: Your Docker Hub username
   - `DOCKER_PASSWORD`: Your Docker Hub password
   - `KUBE_CONFIG_BASE64`: Base64 encoded kubeconfig

```bash
# Generate KUBE_CONFIG_BASE64
cat k3s-kubeconfig.yaml | base64 | pbcopy
```

### Deployment Process
1. Push to main branch triggers build
2. Services are containerized and pushed to Docker Hub
3. K3s deployments are updated with new images
4. Rolling updates ensure zero downtime

## Security Measures

### Immediate Actions Required
1. **Generate new SSH key pair** (old one was exposed)
   ```bash
   # On EC2
   sudo su -
   ssh-keygen -t ed25519 -f /root/.ssh/munbon-deploy-key
   # Add public key to authorized_keys
   ```

2. **Set up AWS Systems Manager** (recommended)
   - No SSH keys needed
   - Audit trail of all access
   - IAM-based authentication

3. **Network Security**
   ```bash
   # Update security group
   # Allow only: 80, 443, 6443 (kubectl)
   # Remove: 22 (SSH) after SSM setup
   ```

## Monitoring Setup

### Install Prometheus & Grafana
```bash
# Apply monitoring stack
kubectl apply -f k8s/monitoring/

# Access Grafana
kubectl port-forward -n monitoring svc/grafana 3000:3000
# Default: admin/admin
```

### Key Metrics to Monitor
- Node resources (CPU, memory, disk)
- Pod resources and restarts
- Service response times
- Database connections
- Message queue lag

## Scaling Strategies

### Vertical Scaling
- Current: t3.large (2 vCPU, 8GB)
- Next: t3.xlarge (4 vCPU, 16GB) - $120/month
- Max: t3.2xlarge (8 vCPU, 32GB) - $241/month

### Horizontal Scaling
1. Add worker nodes:
   ```bash
   # On new EC2 instance
   curl -sfL https://get.k3s.io | K3S_URL=https://43.209.22.250:6443 K3S_TOKEN=<token> sh -
   ```

2. Use node selectors:
   ```yaml
   nodeSelector:
     node-role.kubernetes.io/worker: "true"
   ```

## Disaster Recovery

### Backup Strategy
1. **Database backups** (daily)
   ```bash
   kubectl exec -n munbon postgres-0 -- pg_dump -U munbon_user munbon_db > backup.sql
   ```

2. **Persistent volumes** (weekly)
   ```bash
   # Snapshot EBS volumes via AWS Console
   ```

3. **K3s cluster state** (on changes)
   ```bash
   kubectl get all --all-namespaces -o yaml > cluster-backup.yaml
   ```

### Recovery Procedures
1. **Service failure**: K8s auto-restarts
2. **Node failure**: Restore from AMI
3. **Data loss**: Restore from backups
4. **Complete failure**: Rebuild from git + backups

## Cost Analysis

### Current Setup (t3.large + storage)
- EC2: $60.48/month
- Storage (100GB): $8/month
- Data transfer: ~$9/month
- **Total**: ~$77/month

### Comparison
- EKS: Would add $144/month (cluster fee)
- ECS Fargate: ~$200-400/month
- Multiple EC2s: ~$180+/month

## Troubleshooting

### Common Issues

1. **Pod not starting**
   ```bash
   kubectl describe pod <pod-name> -n munbon
   kubectl logs <pod-name> -n munbon
   ```

2. **Out of resources**
   ```bash
   kubectl top nodes
   kubectl top pods -n munbon
   ```

3. **Service unreachable**
   ```bash
   kubectl get svc -n munbon
   kubectl get endpoints -n munbon
   ```

### Useful Commands
```bash
# Enter pod shell
kubectl exec -it <pod-name> -n munbon -- /bin/bash

# Copy files
kubectl cp <pod-name>:/path/to/file ./local-file -n munbon

# Force restart
kubectl rollout restart deployment/<name> -n munbon

# Emergency scale down
kubectl scale deployment --all --replicas=0 -n munbon
```

## Next Steps

1. **Immediate**
   - [ ] Generate new SSH keys
   - [ ] Update GitHub secrets
   - [ ] Deploy first services

2. **This Week**
   - [ ] Set up monitoring
   - [ ] Configure backups
   - [ ] Load testing

3. **This Month**
   - [ ] AWS Systems Manager
   - [ ] SSL certificates
   - [ ] Multi-node setup

## Support

For issues or questions:
1. Check pod logs first
2. Review this guide
3. Check K3s docs: https://k3s.io
4. Contact DevOps team