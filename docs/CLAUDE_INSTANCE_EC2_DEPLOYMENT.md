# Claude Instance - EC2 Deployment Specialist

## Mission
Fix the broken EC2 deployment pipeline and implement a production-ready, secure, and scalable infrastructure for the Munbon Irrigation Control System using K3s on the existing EC2 instance.

## Current Situation Analysis

### Problems Identified (Past 3-4 Days)
1. **SSH Key Management Chaos**
   - Private key exposed in GITHUB_SECRETS_SETUP.md
   - Multiple failed attempts with base64 encoding
   - GitHub Actions workflows failing due to key format issues

2. **Deployment Approach Issues**
   - Using basic docker-compose for production
   - Trying to run 15+ services on single EC2
   - No health checks or automatic recovery
   - Manual deployment prone to errors

3. **Security Vulnerabilities**
   - Hardcoded credentials in docker-compose files
   - SSH key in repository documentation
   - No proper secrets management
   - Direct SSH access from GitHub Actions

## Recommended Solution: K3s on EC2

### Why K3s?
- **Lightweight**: Only 512MB RAM overhead
- **Production-ready**: Used by thousands of organizations
- **Cost-effective**: No additional infrastructure needed
- **Feature-rich**: Includes Traefik, CoreDNS, metrics-server
- **Easy management**: Single binary, simple upgrades

### Infrastructure Overview
```
┌─────────────────────────────────────────────────────────────┐
│                    EC2 Instance (t3.large)                  │
│                         43.209.22.250                       │
├─────────────────────────────────────────────────────────────┤
│                         K3s Master                          │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐  │
│  │   Traefik   │  │   CoreDNS    │  │  Metrics Server │  │
│  │(Ingress LB) │  │(Internal DNS)│  │  (Monitoring)   │  │
│  └─────────────┘  └──────────────┘  └─────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│                     Application Pods                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│  │   Auth   │  │   GIS    │  │  Sensor  │  │    AI    │ │
│  │ Service  │  │ Service  │  │   Data   │  │  Models  │ │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘ │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│  │  Water   │  │  SCADA   │  │ Weather  │  │Notification│
│  │ Control  │  │Integration│ │Integration│ │  Service  │ │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘ │
├─────────────────────────────────────────────────────────────┤
│                    StatefulSets (Data)                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│  │PostgreSQL│  │TimescaleDB│ │  MongoDB │  │  Redis   │ │
│  │          │  │           │ │          │  │          │ │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## Implementation Plan

### Phase 1: Security Fixes (Day 1)

#### 1.1 Remove Exposed SSH Key
```bash
# On EC2 instance
# Generate new key pair
ssh-keygen -t rsa -b 4096 -f ~/.ssh/munbon-deploy-key -N ""

# Add to authorized_keys
cat ~/.ssh/munbon-deploy-key.pub >> ~/.ssh/authorized_keys

# Remove old key
# Update security group to restrict SSH access
```

#### 1.2 Set Up AWS Systems Manager
```bash
# Install SSM Agent (if not already installed)
sudo snap install amazon-ssm-agent --classic

# Create IAM role for EC2 with SSM permissions
# Attach role to EC2 instance
```

#### 1.3 Configure AWS CLI Access
```yaml
# GitHub Actions secrets needed:
AWS_ACCESS_KEY_ID: <your-key>
AWS_SECRET_ACCESS_KEY: <your-secret>
AWS_DEFAULT_REGION: ap-southeast-1
EC2_INSTANCE_ID: i-xxxxxxxxx
```

### Phase 2: K3s Installation (Day 1)

#### 2.1 Install K3s
```bash
# On EC2 instance
curl -sfL https://get.k3s.io | sh -s - \
  --write-kubeconfig-mode 644 \
  --disable traefik \
  --node-name munbon-master

# Install Traefik 2 with custom config
kubectl apply -f https://raw.githubusercontent.com/traefik/traefik/v2.10/docs/content/reference/dynamic-configuration/kubernetes-crd-definition-v1.yml
```

#### 2.2 Configure kubectl Access
```bash
# Copy kubeconfig to local machine
scp ubuntu@43.209.22.250:/etc/rancher/k3s/k3s.yaml ~/.kube/munbon-k3s.yaml

# Update server address in config
sed -i 's/127.0.0.1/43.209.22.250/g' ~/.kube/munbon-k3s.yaml

# Use config
export KUBECONFIG=~/.kube/munbon-k3s.yaml
```

### Phase 3: Service Deployment (Day 2)

#### 3.1 Namespace Setup
```yaml
# namespaces.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: munbon-prod
---
apiVersion: v1
kind: Namespace
metadata:
  name: munbon-data
---
apiVersion: v1
kind: Namespace
metadata:
  name: munbon-monitoring
```

#### 3.2 Database Deployments
```yaml
# postgres-statefulset.yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgres
  namespace: munbon-data
spec:
  serviceName: postgres
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
      - name: postgres
        image: postgis/postgis:15-3.3
        ports:
        - containerPort: 5432
        env:
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: postgres-secret
              key: password
        volumeMounts:
        - name: postgres-storage
          mountPath: /var/lib/postgresql/data
        resources:
          requests:
            memory: "1Gi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
  volumeClaimTemplates:
  - metadata:
      name: postgres-storage
    spec:
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 20Gi
```

#### 3.3 Application Deployments
```yaml
# auth-service-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: auth-service
  namespace: munbon-prod
spec:
  replicas: 2
  selector:
    matchLabels:
      app: auth-service
  template:
    metadata:
      labels:
        app: auth-service
    spec:
      containers:
      - name: auth-service
        image: subhaj888/munbon-auth:latest
        ports:
        - containerPort: 3000
        env:
        - name: NODE_ENV
          value: production
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: db-credentials
              key: auth-db-url
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 3000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 3000
          initialDelaySeconds: 5
          periodSeconds: 5
```

### Phase 4: Monitoring Setup (Day 2)

#### 4.1 Prometheus Stack
```bash
# Install using Helm
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install monitoring prometheus-community/kube-prometheus-stack \
  --namespace munbon-monitoring \
  --set grafana.adminPassword=your-secure-password
```

#### 4.2 Custom Dashboards
```yaml
# grafana-dashboard-configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: munbon-dashboards
  namespace: munbon-monitoring
data:
  munbon-overview.json: |
    {
      "dashboard": {
        "title": "Munbon System Overview",
        "panels": [...]
      }
    }
```

### Phase 5: CI/CD Pipeline (Day 3)

#### 5.1 GitHub Actions Workflow
```yaml
# .github/workflows/deploy-k3s.yml
name: Deploy to K3s

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v1
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ap-southeast-1
      
      - name: Build and push to ECR
        env:
          ECR_REGISTRY: ${{ secrets.ECR_REGISTRY }}
        run: |
          aws ecr get-login-password | docker login --username AWS --password-stdin $ECR_REGISTRY
          docker build -t $ECR_REGISTRY/munbon/$SERVICE:$GITHUB_SHA .
          docker push $ECR_REGISTRY/munbon/$SERVICE:$GITHUB_SHA
      
      - name: Deploy to K3s
        run: |
          # Use AWS SSM to run kubectl commands
          aws ssm send-command \
            --instance-ids "${{ secrets.EC2_INSTANCE_ID }}" \
            --document-name "AWS-RunShellScript" \
            --parameters 'commands=["kubectl set image deployment/auth-service auth-service=$ECR_REGISTRY/munbon/auth:$GITHUB_SHA -n munbon-prod"]'
```

### Phase 6: Backup & Recovery (Day 3)

#### 6.1 Database Backups
```yaml
# postgres-backup-cronjob.yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: postgres-backup
  namespace: munbon-data
spec:
  schedule: "0 2 * * *"  # Daily at 2 AM
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: postgres-backup
            image: postgres:15
            command:
            - /bin/bash
            - -c
            - |
              pg_dump -h postgres -U postgres munbon_prod | \
              aws s3 cp - s3://munbon-backups/postgres/$(date +%Y%m%d_%H%M%S).sql
```

## Security Checklist

- [ ] Remove exposed SSH key from all documentation
- [ ] Generate new SSH key pair
- [ ] Configure AWS Systems Manager
- [ ] Set up IAM roles (not keys) where possible
- [ ] Implement K8s network policies
- [ ] Enable audit logging
- [ ] Configure security groups properly
- [ ] Use AWS Secrets Manager for sensitive data
- [ ] Enable CloudWatch logging
- [ ] Set up vulnerability scanning

## Cost Analysis

### Current Setup
- EC2 t3.large: $60.48/month
- Total: $60.48/month

### With K3s
- EC2 t3.large: $60.48/month
- EBS storage (100GB): $8/month
- Data transfer: ~$9/month
- Total: $77.48/month

### Comparison
- vs EKS: Save $144+/month
- vs ECS Fargate: Save $150-300+/month
- vs Multiple EC2s: Save $120+/month

## Troubleshooting Guide

### Common Issues

1. **K3s won't start**
   ```bash
   # Check logs
   journalctl -u k3s -f
   
   # Verify system requirements
   free -h  # Should have >512MB free
   ```

2. **Pods not scheduling**
   ```bash
   # Check node status
   kubectl get nodes
   kubectl describe node munbon-master
   
   # Check resource usage
   kubectl top nodes
   ```

3. **Service unreachable**
   ```bash
   # Check service and endpoints
   kubectl get svc,ep -A
   
   # Check ingress
   kubectl get ingress -A
   ```

## Success Metrics

- [ ] All services deployed and running
- [ ] Zero SSH key exposure
- [ ] Automated deployment pipeline working
- [ ] Monitoring dashboards accessible
- [ ] Sub-second response times achieved
- [ ] 99.9% uptime maintained
- [ ] Automatic scaling functional
- [ ] Disaster recovery tested

## Next Steps

1. Start with security fixes immediately
2. Install K3s on EC2
3. Deploy core services first (auth, sensor-data, GIS)
4. Add monitoring stack
5. Implement automated deployments
6. Document runbooks
7. Train team on K3s operations

Remember: This is critical infrastructure. Every minute of downtime affects farmers' irrigation schedules!