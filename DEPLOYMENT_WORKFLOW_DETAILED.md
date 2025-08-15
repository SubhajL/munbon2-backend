# Detailed Deployment Workflow: Local to EC2/K3s

## Overview
This document explains exactly how code from your local machine gets deployed to the K3s cluster running on EC2.

## 🏗️ Architecture Overview

```
Local Development → GitHub → Docker Hub → K3s on EC2
     (You)         (VCS)    (Registry)   (Runtime)
```

## 📋 Prerequisites Setup

### 1. Local Development Environment
```bash
# Your local machine needs:
- Git (for version control)
- Docker (for building images locally - optional)
- kubectl (for manual deployments)
- Code editor (VS Code, etc.)
```

### 2. GitHub Repository Setup
```bash
# Your repository structure:
/munbon2-backend/
├── services/
│   ├── auth-service/
│   │   ├── Dockerfile
│   │   ├── package.json
│   │   └── src/
│   ├── gis-service/
│   │   ├── Dockerfile
│   │   └── src/
│   └── ... (other services)
├── k8s/
│   ├── base/
│   └── services/
└── .github/workflows/deploy-k3s.yml
```

### 3. Required Secrets in GitHub
Go to: https://github.com/SubhajL/munbon2-backend/settings/secrets/actions

Add these secrets:
- `DOCKER_USERNAME`: Your Docker Hub username
- `DOCKER_PASSWORD`: Your Docker Hub password  
- `KUBE_CONFIG_BASE64`: Base64 encoded kubeconfig file

```bash
# Generate KUBE_CONFIG_BASE64:
cat k3s-kubeconfig.yaml | base64 | pbcopy  # macOS
# Then paste into GitHub Secrets
```

## 🚀 Deployment Methods

### Method 1: Automatic Deployment (GitHub Actions)

#### Step 1: Develop Your Code
```bash
# Make changes to a service
cd services/auth-service
# Edit your code files
vim src/index.js
```

#### Step 2: Commit and Push
```bash
# Stage your changes
git add .

# Commit with descriptive message
git commit -m "feat: add user validation to auth service"

# Push to main branch (triggers deployment)
git push origin main
```

#### Step 3: GitHub Actions Workflow Executes
The workflow (`.github/workflows/deploy-k3s.yml`) automatically:

1. **Checks out code**
   ```yaml
   - uses: actions/checkout@v4
   ```

2. **Builds Docker images**
   ```bash
   # For each service with a Dockerfile:
   docker build -t docker.io/yourusername/auth-service:git-sha ./services/auth-service
   ```

3. **Pushes to Docker Hub**
   ```bash
   docker push docker.io/yourusername/auth-service:git-sha
   docker push docker.io/yourusername/auth-service:latest
   ```

4. **Deploys to K3s**
   ```bash
   # Uses the KUBE_CONFIG to connect
   kubectl set image deployment/auth-service auth-service=docker.io/yourusername/auth-service:git-sha -n munbon
   ```

#### Step 4: Monitor Deployment
```bash
# Watch the GitHub Actions run
# Go to: https://github.com/SubhajL/munbon2-backend/actions

# Or check from command line
gh run list
gh run view
```

### Method 2: Manual Deployment (Direct)

#### Step 1: Build Docker Image Locally
```bash
cd services/auth-service

# Build the image
docker build -t munbon/auth-service:v1.0 .

# Test locally (optional)
docker run -p 3000:3000 munbon/auth-service:v1.0
```

#### Step 2: Push to Registry
```bash
# Login to Docker Hub
docker login

# Tag for Docker Hub
docker tag munbon/auth-service:v1.0 yourusername/auth-service:v1.0

# Push image
docker push yourusername/auth-service:v1.0
```

#### Step 3: Deploy to K3s
```bash
# Set kubeconfig
export KUBECONFIG=./k3s-kubeconfig.yaml

# Apply the deployment
kubectl apply -f k8s/services/auth-service.yaml

# Or update existing deployment
kubectl set image deployment/auth-service auth-service=yourusername/auth-service:v1.0 -n munbon
```

#### Step 4: Verify Deployment
```bash
# Check rollout status
kubectl rollout status deployment/auth-service -n munbon

# Check pods
kubectl get pods -n munbon

# Check logs
kubectl logs -l app=auth-service -n munbon
```

## 📝 Detailed Deployment Flow

### 1. Code Development Phase
```bash
# Developer works on local machine
cd ~/dev/munbon2-backend/services/auth-service

# Make changes
code src/controllers/auth.controller.js

# Test locally
npm test
npm run dev
```

### 2. Containerization Phase
```dockerfile
# Dockerfile for auth-service
FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY . .
EXPOSE 3000
CMD ["node", "index.js"]
```

### 3. Version Control Phase
```bash
# Check what changed
git status
git diff

# Stage and commit
git add -A
git commit -m "fix: resolve JWT token expiration issue"

# Push to GitHub
git push origin main
```

### 4. CI/CD Pipeline Phase (Automatic)
GitHub Actions workflow triggers:

```yaml
name: Deploy to K3s
on:
  push:
    branches: [main]

jobs:
  build-and-push:
    runs-on: ubuntu-latest
    steps:
      # 1. Get the code
      - uses: actions/checkout@v4
      
      # 2. Setup Docker
      - uses: docker/setup-buildx-action@v3
      
      # 3. Login to registry
      - uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKER_USERNAME }}
          password: ${{ secrets.DOCKER_PASSWORD }}
      
      # 4. Build and push each service
      - run: |
          docker build -t $USERNAME/auth-service:$GITHUB_SHA ./services/auth-service
          docker push $USERNAME/auth-service:$GITHUB_SHA
```

### 5. Deployment Phase
The workflow continues:

```yaml
  deploy:
    needs: build-and-push
    steps:
      # 1. Setup kubectl with K3s config
      - run: |
          echo "${{ secrets.KUBE_CONFIG_BASE64 }}" | base64 -d > kubeconfig
          export KUBECONFIG=./kubeconfig
      
      # 2. Update the deployment
      - run: |
          kubectl set image deployment/auth-service \
            auth-service=$USERNAME/auth-service:$GITHUB_SHA \
            -n munbon
      
      # 3. Wait for rollout
      - run: |
          kubectl rollout status deployment/auth-service -n munbon
```

### 6. K3s Execution Phase
On the EC2 instance, K3s:

1. **Pulls the new image**
   ```bash
   # K3s pulls from Docker Hub
   docker.io/yourusername/auth-service:abc123
   ```

2. **Creates new pods**
   ```bash
   # Rolling update strategy
   # Creates new pod with new image
   # Waits for it to be ready
   # Terminates old pod
   ```

3. **Updates service endpoints**
   ```bash
   # Traffic automatically routes to new pods
   # Zero downtime deployment
   ```

## 🔄 Complete Example: Deploying Auth Service

### Step 1: Create the Service Code
```bash
# Create service directory
mkdir -p services/auth-service/src

# Create main file
cat > services/auth-service/src/index.js << 'EOF'
const express = require('express');
const app = express();

app.get('/health', (req, res) => {
  res.json({ status: 'healthy', service: 'auth', version: '1.0.0' });
});

app.listen(3000, () => {
  console.log('Auth service running on port 3000');
});
EOF

# Create package.json
cat > services/auth-service/package.json << 'EOF'
{
  "name": "auth-service",
  "version": "1.0.0",
  "main": "src/index.js",
  "dependencies": {
    "express": "^4.18.0"
  }
}
EOF
```

### Step 2: Create Dockerfile
```bash
cat > services/auth-service/Dockerfile << 'EOF'
FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install --production
COPY . .
EXPOSE 3000
CMD ["node", "src/index.js"]
EOF
```

### Step 3: Create K8s Manifest
```bash
# This is already created at k8s/services/auth-service.yaml
# It defines how the service runs in K3s
```

### Step 4: Commit and Push
```bash
git add services/auth-service/
git commit -m "feat: add auth service with health endpoint"
git push origin main
```

### Step 5: GitHub Actions Automatically:
1. Builds Docker image
2. Tags it with commit SHA
3. Pushes to Docker Hub
4. Updates K3s deployment
5. Monitors rollout

### Step 6: Verify on EC2
```bash
# SSH to EC2 (or use kubectl locally)
ssh -i your-key.pem ubuntu@43.209.22.250

# Check the deployment
sudo kubectl get pods -n munbon
sudo kubectl logs -l app=auth-service -n munbon

# Test the service
sudo kubectl port-forward svc/auth-service 3000:80 -n munbon
curl http://localhost:3000/health
```

## 🛠️ Manual Deployment Commands

### Deploy All Services
```bash
# From your local machine
export KUBECONFIG=./k3s-kubeconfig.yaml

# Deploy everything
./scripts/deploy-k3s.sh
```

### Deploy Single Service
```bash
# Just auth service
kubectl apply -f k8s/services/auth-service.yaml

# Update image for existing service
kubectl set image deployment/auth-service \
  auth-service=yourusername/auth-service:new-tag \
  -n munbon
```

### Emergency Rollback
```bash
# Rollback to previous version
kubectl rollout undo deployment/auth-service -n munbon

# Check rollout history
kubectl rollout history deployment/auth-service -n munbon
```

## 📊 Monitoring Deployments

### Check Deployment Status
```bash
# All deployments
kubectl get deployments -n munbon

# Specific service
kubectl describe deployment auth-service -n munbon

# Pod status
kubectl get pods -n munbon -w
```

### View Logs
```bash
# All logs for a service
kubectl logs -l app=auth-service -n munbon

# Follow logs
kubectl logs -f deployment/auth-service -n munbon

# Previous pod logs (after crash)
kubectl logs deployment/auth-service -n munbon --previous
```

### Debug Issues
```bash
# Get pod details
kubectl describe pod auth-service-xxx -n munbon

# Enter pod shell
kubectl exec -it auth-service-xxx -n munbon -- /bin/sh

# Check events
kubectl get events -n munbon --sort-by='.lastTimestamp'
```

## 🔑 Key Points

1. **Code** → **GitHub** → **Docker Hub** → **K3s**
2. **Automatic**: Push to main = Auto deploy
3. **Manual**: Build, push, kubectl apply
4. **Zero downtime**: Rolling updates
5. **Rollback**: One command to previous version

## 🚨 Troubleshooting

### Build Fails
```bash
# Check Dockerfile syntax
docker build -t test ./services/auth-service

# Check GitHub Actions logs
```

### Deployment Fails
```bash
# Check image exists
docker pull yourusername/auth-service:tag

# Check K3s can pull
kubectl describe pod <failing-pod> -n munbon
```

### Service Unreachable
```bash
# Check service endpoints
kubectl get endpoints -n munbon

# Check pod is running
kubectl get pods -n munbon

# Check service definition
kubectl get svc auth-service -n munbon -o yaml
```

## 📚 Summary

1. **Write code** locally
2. **Git push** to GitHub
3. **GitHub Actions** builds Docker images
4. **Docker images** pushed to Docker Hub
5. **K3s pulls** new images
6. **Rolling update** with zero downtime
7. **Service available** on EC2

The entire process is automated after git push!