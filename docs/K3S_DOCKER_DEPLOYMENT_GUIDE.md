# Complete K3s + Docker Automated Deployment Guide

## Overview
K3s runs Docker containers using containerd (not Docker daemon). Your Docker images work perfectly, but the deployment process is different from docker-compose.

## Full Deployment Pipeline

```
GitHub → Build Docker Image → Push to Registry → K3s pulls & deploys → Auto-updates
```

## Step 1: Install K3s on EC2

```bash
# SSH to your t3.large
ssh -i th-lab01.pem ubuntu@43.209.22.250

# Install K3s (30 seconds)
curl -sfL https://get.k3s.io | sh -

# Verify installation
sudo k3s kubectl get nodes
# Should show: NAME STATUS ROLES AGE VERSION
```

## Step 2: Convert Docker Compose to K3s Manifests

### Your docker-compose.yml:
```yaml
version: '3.8'
services:
  sensor-data:
    image: subhaj888/munbon-sensor-data:latest
    ports:
      - "3001:3001"
    environment:
      NODE_ENV: production
```

### Becomes K3s deployment.yaml:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: sensor-data
  namespace: munbon
spec:
  replicas: 1
  selector:
    matchLabels:
      app: sensor-data
  template:
    metadata:
      labels:
        app: sensor-data
    spec:
      containers:
      - name: sensor-data
        image: subhaj888/munbon-sensor-data:latest
        imagePullPolicy: Always  # Always pull latest
        ports:
        - containerPort: 3001
        env:
        - name: NODE_ENV
          value: "production"
        - name: DATABASE_URL
          value: "postgresql://postgres:postgres123@postgres:5432/munbon_db"
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "200m"
---
apiVersion: v1
kind: Service
metadata:
  name: sensor-data
  namespace: munbon
spec:
  type: NodePort
  ports:
  - port: 3001
    targetPort: 3001
    nodePort: 30001  # External port
  selector:
    app: sensor-data
```

## Step 3: Automated Deployment with GitHub Actions

### Create `.github/workflows/deploy-k3s.yml`:
```yaml
name: Deploy to K3s

on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
      # Build and push to Docker Hub
      - name: Checkout
        uses: actions/checkout@v4
        
      - name: Login to Docker Hub
        uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKERHUB_USERNAME }}
          password: ${{ secrets.DOCKERHUB_TOKEN }}
      
      - name: Build and push sensor-data
        run: |
          cd services/sensor-data
          docker build -t subhaj888/munbon-sensor-data:latest .
          docker push subhaj888/munbon-sensor-data:latest
      
      # Deploy to K3s
      - name: Deploy to K3s
        env:
          KUBE_CONFIG: ${{ secrets.KUBE_CONFIG_BASE64 }}
        run: |
          # Setup kubeconfig
          echo "$KUBE_CONFIG" | base64 -d > kubeconfig
          export KUBECONFIG=$(pwd)/kubeconfig
          
          # Apply manifests
          kubectl apply -f k8s/namespace.yaml
          kubectl apply -f k8s/postgres.yaml
          kubectl apply -f k8s/sensor-data.yaml
          
          # Force rollout to get new image
          kubectl rollout restart deployment/sensor-data -n munbon
          
          # Wait for rollout
          kubectl rollout status deployment/sensor-data -n munbon
```

## Step 4: Get Kubeconfig for GitHub Actions

```bash
# On your EC2
sudo cat /etc/rancher/k3s/k3s.yaml > kubeconfig

# Replace localhost with your EC2 IP
sed -i 's/127.0.0.1/43.209.22.250/g' kubeconfig

# Encode for GitHub secret
base64 -w 0 kubeconfig

# Copy output and add as KUBE_CONFIG_BASE64 secret in GitHub
```

## Step 5: K3s Manifest Structure

### Create `k8s/` directory:
```
k8s/
├── namespace.yaml
├── postgres.yaml
├── redis.yaml
├── sensor-data.yaml
├── auth.yaml
├── gis.yaml
└── ingress.yaml
```

### namespace.yaml:
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: munbon
```

### postgres.yaml:
```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgres
  namespace: munbon
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
        image: postgres:14
        env:
        - name: POSTGRES_PASSWORD
          value: "postgres123"
        - name: POSTGRES_DB
          value: "munbon_db"
        volumeMounts:
        - name: postgres-data
          mountPath: /var/lib/postgresql/data
  volumeClaimTemplates:
  - metadata:
      name: postgres-data
    spec:
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 10Gi
---
apiVersion: v1
kind: Service
metadata:
  name: postgres
  namespace: munbon
spec:
  ports:
  - port: 5432
  selector:
    app: postgres
```

## Step 6: Auto-update with ImagePullPolicy

### Option A: Always Pull Latest
```yaml
spec:
  containers:
  - name: sensor-data
    image: subhaj888/munbon-sensor-data:latest
    imagePullPolicy: Always  # Pulls on every restart
```

### Option B: Use Specific Tags
```yaml
# In GitHub Actions
docker tag subhaj888/munbon-sensor-data:latest subhaj888/munbon-sensor-data:v${GITHUB_RUN_NUMBER}
docker push subhaj888/munbon-sensor-data:v${GITHUB_RUN_NUMBER}

# Update K3s
kubectl set image deployment/sensor-data sensor-data=subhaj888/munbon-sensor-data:v${GITHUB_RUN_NUMBER} -n munbon
```

## Step 7: Automated Rollouts

### Method 1: Force Restart (Simple)
```bash
kubectl rollout restart deployment/sensor-data -n munbon
```

### Method 2: Flux CD (Advanced - Fully Automated)
```bash
# Install Flux on K3s
curl -s https://fluxcd.io/install.sh | sudo bash

# Bootstrap Flux to watch your repo
flux bootstrap github \
  --owner=SubhajL \
  --repository=munbon2-backend \
  --path=k8s \
  --personal
```

Flux automatically deploys when you push changes!

## Step 8: Access Your Services

### Direct NodePort Access:
```
http://43.209.22.250:30001  # sensor-data
http://43.209.22.250:30002  # auth
http://43.209.22.250:30003  # gis
```

### Or use Traefik Ingress (included in K3s):
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: munbon-ingress
  namespace: munbon
spec:
  rules:
  - host: api.munbon.com
    http:
      paths:
      - path: /sensor
        pathType: Prefix
        backend:
          service:
            name: sensor-data
            port:
              number: 3001
```

## Complete Deployment Script

### Save as `deploy-to-k3s.sh`:
```bash
#!/bin/bash
set -e

# Configuration
K3S_SERVER="43.209.22.250"
SSH_KEY="th-lab01.pem"
SERVICES=("sensor-data" "auth" "gis")

echo "🚀 Deploying to K3s..."

# Build and push all services
for service in "${SERVICES[@]}"; do
  echo "📦 Building $service..."
  cd services/$service
  docker build -t subhaj888/munbon-$service:latest .
  docker push subhaj888/munbon-$service:latest
  cd ../..
done

# Deploy to K3s
echo "🎯 Deploying to K3s cluster..."
scp -i $SSH_KEY -r k8s/ ubuntu@$K3S_SERVER:/tmp/

ssh -i $SSH_KEY ubuntu@$K3S_SERVER << 'EOF'
  cd /tmp/k8s
  sudo k3s kubectl apply -f namespace.yaml
  sudo k3s kubectl apply -f .
  
  # Restart deployments to pull new images
  sudo k3s kubectl rollout restart deployment --all -n munbon
  
  # Wait for rollout
  sudo k3s kubectl rollout status deployment --all -n munbon
  
  echo "✅ Deployment complete!"
  sudo k3s kubectl get pods -n munbon
EOF
```

## Monitoring and Debugging

### Check status:
```bash
# All pods
sudo k3s kubectl get pods -n munbon

# Logs
sudo k3s kubectl logs deployment/sensor-data -n munbon

# Describe pod (for errors)
sudo k3s kubectl describe pod sensor-data-xxx -n munbon

# Resource usage
sudo k3s kubectl top nodes
sudo k3s kubectl top pods -n munbon
```

### Auto-scaling (HPA):
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: sensor-data-hpa
  namespace: munbon
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: sensor-data
  minReplicas: 1
  maxReplicas: 3
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

## Advantages Over Docker Compose

1. **Self-healing**: Containers restart automatically
2. **Rolling updates**: Zero-downtime deployments
3. **Scaling**: `kubectl scale deployment/sensor-data --replicas=3`
4. **Load balancing**: Built-in service discovery
5. **Resource limits**: Prevents one service from killing others
6. **Health checks**: Automatic restarts on failure

## Quick Commands Cheat Sheet

```bash
# Deploy everything
kubectl apply -f k8s/

# Update single service
kubectl rollout restart deployment/sensor-data -n munbon

# Scale service
kubectl scale deployment/sensor-data --replicas=3 -n munbon

# View logs
kubectl logs -f deployment/sensor-data -n munbon

# SSH into pod
kubectl exec -it sensor-data-xxx -n munbon -- /bin/sh

# Delete everything
kubectl delete namespace munbon
```

This is the complete automated deployment process with K3s!