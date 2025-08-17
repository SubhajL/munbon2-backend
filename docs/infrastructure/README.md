# Infrastructure

This directory contains all infrastructure-related configurations and deployment files.

## Structure

### kubernetes
Kubernetes manifests for deploying the system:
- **base** - Base configurations (namespaces, configmaps, secrets)
- **services** - Service-specific deployments and services
- **databases** - Database StatefulSets and PersistentVolumes
- **monitoring** - Prometheus, Grafana, and other monitoring tools

### docker
Docker-related configurations:
- Docker Compose files for local development
- Database initialization scripts
- Custom Docker images

### terraform
Infrastructure as Code for cloud resources:
- **modules** - Reusable Terraform modules
- **environments** - Environment-specific configurations

### helm
Helm charts for Kubernetes deployments:
- **munbon-backend** - Main application Helm chart

## Deployment

### Local Development
```bash
cd docker
docker-compose up -d
```

### Kubernetes Deployment
```bash
kubectl apply -f kubernetes/base/
kubectl apply -f kubernetes/services/
kubectl apply -f kubernetes/databases/
```

### Terraform Deployment
```bash
cd terraform/environments/production
terraform init
terraform plan
terraform apply
```

## Important Notes

- Always use ConfigMaps and Secrets for configuration
- Follow the principle of least privilege for RBAC
- Ensure all resources have appropriate resource limits
- Use separate namespaces for different environments