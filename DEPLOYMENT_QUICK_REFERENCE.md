# Deployment Quick Reference

## 🚀 Quick Deploy Commands

### First Time Setup
```bash
# 1. Get kubeconfig from EC2
scp ubuntu@43.209.22.250:/home/ubuntu/k3s-kubeconfig.yaml ./

# 2. Set environment
export KUBECONFIG=./k3s-kubeconfig.yaml

# 3. Verify connection
kubectl get nodes
```

### Daily Development Flow

#### Option A: Automatic (Recommended)
```bash
# 1. Make changes
cd services/auth-service
# ... edit code ...

# 2. Deploy automatically
git add .
git commit -m "feat: your changes"
git push origin main

# ✅ GitHub Actions handles everything!
```

#### Option B: Manual Deploy
```bash
# 1. Build locally
cd services/auth-service
docker build -t yourdockerhub/auth-service:v1 .

# 2. Push to registry
docker push yourdockerhub/auth-service:v1

# 3. Deploy to K3s
kubectl set image deployment/auth-service \
  auth-service=yourdockerhub/auth-service:v1 -n munbon
```

## 📁 Project Structure

```
/munbon2-backend/
├── services/               # Your microservices
│   ├── auth-service/      
│   │   ├── Dockerfile     # How to build
│   │   ├── src/          # Your code
│   │   └── package.json   
│   └── [other-services]/  
├── k8s/                   # Kubernetes configs
│   ├── services/         # Deployment manifests
│   └── base/            # Shared configs
├── .github/              
│   └── workflows/        
│       └── deploy-k3s.yml # Auto-deployment
└── scripts/              
    └── deploy-k3s.sh     # Manual deploy script
```

## 🔄 Deployment Flow

```
1. You code locally ✏️
       ↓
2. Git push 📤
       ↓
3. GitHub Actions 🤖
   - Builds Docker image
   - Pushes to Docker Hub
       ↓
4. Deploys to K3s 🚀
   - Updates deployment
   - Rolling update
       ↓
5. Running on EC2! ✅
```

## 🏃 Common Tasks

### Check What's Running
```bash
# All services
kubectl get all -n munbon

# Specific service
kubectl get deployment auth-service -n munbon
kubectl get pods -l app=auth-service -n munbon
```

### View Logs
```bash
# Service logs
kubectl logs -l app=auth-service -n munbon

# Follow logs (real-time)
kubectl logs -f deployment/auth-service -n munbon
```

### Scale Service
```bash
# Scale up
kubectl scale deployment/auth-service --replicas=3 -n munbon

# Scale down
kubectl scale deployment/auth-service --replicas=1 -n munbon
```

### Update Service
```bash
# Quick update (manual)
kubectl set image deployment/auth-service \
  auth-service=yourdockerhub/auth-service:v2 -n munbon

# Full update (with manifest)
kubectl apply -f k8s/services/auth-service.yaml
```

### Rollback
```bash
# Undo last deployment
kubectl rollout undo deployment/auth-service -n munbon

# Check history
kubectl rollout history deployment/auth-service -n munbon
```

## 🔧 Debug Commands

### Pod Not Starting?
```bash
# Check pod status
kubectl describe pod <pod-name> -n munbon

# Check events
kubectl get events -n munbon --sort-by='.lastTimestamp'
```

### Can't Pull Image?
```bash
# Check image name in deployment
kubectl get deployment auth-service -n munbon -o yaml | grep image:

# Try pulling manually on EC2
ssh ubuntu@43.209.22.250
sudo docker pull yourdockerhub/auth-service:tag
```

### Service Not Responding?
```bash
# Check endpoints
kubectl get endpoints auth-service -n munbon

# Test from inside cluster
kubectl run test --rm -it --image=busybox -- /bin/sh
wget -O- http://auth-service.munbon.svc.cluster.local
```

## 📋 GitHub Secrets Required

1. Go to: https://github.com/SubhajL/munbon2-backend/settings/secrets/actions
2. Add:
   - `DOCKER_USERNAME`: Your Docker Hub username
   - `DOCKER_PASSWORD`: Your Docker Hub password
   - `KUBE_CONFIG_BASE64`: Run `cat k3s-kubeconfig.yaml | base64`

## 🚨 Emergency Procedures

### Stop Everything
```bash
# Scale all to zero
kubectl scale deployment --all --replicas=0 -n munbon
```

### Restart Service
```bash
# Delete pods (they auto-recreate)
kubectl delete pods -l app=auth-service -n munbon
```

### Full Reset
```bash
# Delete and recreate
kubectl delete deployment auth-service -n munbon
kubectl apply -f k8s/services/auth-service.yaml
```

## 💡 Pro Tips

1. **Always check GitHub Actions** after pushing
   - https://github.com/SubhajL/munbon2-backend/actions

2. **Use labels** for easy filtering
   ```bash
   kubectl get pods -l service=core -n munbon
   ```

3. **Dry run** before applying
   ```bash
   kubectl apply -f k8s/services/auth-service.yaml --dry-run=client
   ```

4. **Watch deployments** in real-time
   ```bash
   kubectl get pods -n munbon -w
   ```

5. **Port forward** for local testing
   ```bash
   kubectl port-forward svc/auth-service 3000:80 -n munbon
   # Now access http://localhost:3000
   ```

## 📞 Quick Support

```bash
# Check cluster health
kubectl get nodes
kubectl top nodes

# Check K3s status on EC2
ssh ubuntu@43.209.22.250 'sudo systemctl status k3s'

# View K3s logs
ssh ubuntu@43.209.22.250 'sudo journalctl -u k3s -f'
```

---
Remember: `git push` = Auto deploy! 🚀