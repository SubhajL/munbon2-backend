# Free Kubernetes Options

## 1. K3s on Your Existing EC2

### Overview
K3s is a lightweight Kubernetes distribution by Rancher. Runs on a single EC2 instance.

### Setup
```bash
# On your EC2 (takes 30 seconds!)
curl -sfL https://get.k3s.io | sh -

# Get kubeconfig
sudo cat /etc/rancher/k3s/k3s.yaml
```

### Cost
- **FREE** (uses your existing $30/month EC2)
- No additional charges

### Pros
- Fully functional Kubernetes
- Very lightweight (500MB RAM)
- Includes Traefik ingress
- Single binary install

### Cons
- Single node (no high availability)
- Limited resources on t2.micro

---

## 2. MicroK8s on EC2

### Overview
Canonical's lightweight Kubernetes for edge/IoT/dev.

### Setup
```bash
# On Ubuntu EC2
sudo snap install microk8s --classic
sudo microk8s enable dns storage ingress
```

### Cost
- **FREE** (uses your existing EC2)

### Pros
- Addons included (dashboard, metrics)
- Easy to use
- Good for development

---

## 3. Kind (Kubernetes in Docker)

### Overview
Runs Kubernetes inside Docker containers on your EC2.

### Setup
```bash
# Install on EC2
curl -Lo ./kind https://kind.sigs.k8s.io/dl/latest/kind-linux-amd64
chmod +x ./kind
sudo mv ./kind /usr/local/bin/

# Create cluster
kind create cluster --name munbon
```

### Cost
- **FREE** (uses your existing EC2)

### Pros
- Real Kubernetes API
- Good for testing
- Multi-node capable

### Cons
- Nested containers (performance)
- Not for production

---

## 4. Docker Swarm (Kubernetes Alternative)

### Overview
Docker's native orchestration - simpler than Kubernetes.

### Setup
```bash
# On your EC2
docker swarm init

# Deploy stack (uses your docker-compose.yml!)
docker stack deploy -c docker-compose.yml munbon
```

### Cost
- **FREE** (built into Docker)

### Example docker-compose for Swarm
```yaml
version: '3.8'
services:
  sensor-data:
    image: subhaj888/munbon-sensor-data:latest
    deploy:
      replicas: 2
      restart_policy:
        condition: on-failure
    ports:
      - "3001:3001"
```

### Pros
- Uses existing docker-compose
- Built into Docker
- Simple to learn
- Good enough for most apps

### Cons
- Not "real" Kubernetes
- Smaller ecosystem

---

## 5. Free Managed Kubernetes Tiers

### DigitalOcean Kubernetes (DOKS)
- Control plane: **FREE**
- Pay only for worker nodes (~$20/month per node)
- $200 free credit for new users

### Linode Kubernetes Engine (LKE)
- Control plane: **FREE**
- Worker nodes from $12/month
- $100 free credit

### Google Kubernetes Engine (GKE) Autopilot
- $74.40 free credit/month for control plane
- Pay per pod (can be very cheap for small workloads)

---

## Comparison Table

| Option | Monthly Cost | Setup Time | Production Ready | Kubernetes Compatible |
|--------|-------------|------------|------------------|---------------------|
| K3s on EC2 | $0 extra | 5 min | Yes (single node) | ✅ Yes |
| MicroK8s | $0 extra | 5 min | Yes (single node) | ✅ Yes |
| Kind | $0 extra | 2 min | No | ✅ Yes |
| Docker Swarm | $0 extra | 1 min | Yes | ❌ No (but similar) |
| DigitalOcean | ~$20/month | 10 min | Yes | ✅ Yes |

---

## Recommendation for Munbon Project

### Best Free Option: K3s on your EC2

1. **Install K3s** (30 seconds)
```bash
curl -sfL https://get.k3s.io | sh -
```

2. **Convert docker-compose to Kubernetes**
```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: sensor-data
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
        ports:
        - containerPort: 3001
---
apiVersion: v1
kind: Service
metadata:
  name: sensor-data
spec:
  type: NodePort
  ports:
  - port: 3001
    nodePort: 30001
  selector:
    app: sensor-data
```

3. **Deploy**
```bash
kubectl apply -f deployment.yaml
```

### Why K3s?
- Real Kubernetes experience
- Upgradeable to EKS later
- Includes load balancer
- Auto-restart on failure
- Rolling updates
- Secret management

### Migration Path
1. Current: docker-compose on EC2
2. Tomorrow: K3s on same EC2 (free!)
3. Future: Move to EKS when you need multi-node

---

## Quick Start Script for K3s

```bash
#!/bin/bash
# Save as setup-k3s.sh and run on EC2

# Install K3s
curl -sfL https://get.k3s.io | sh -

# Wait for K3s to be ready
sudo k3s kubectl wait --for=condition=Ready node --all

# Create namespace
sudo k3s kubectl create namespace munbon

# Install cert-manager for HTTPS
sudo k3s kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml

echo "K3s installed! Your cluster is ready."
echo "Deploy apps with: sudo k3s kubectl apply -f your-app.yaml"
```

---

## Docker Swarm (Simplest Alternative)

If Kubernetes seems complex, Docker Swarm is even simpler:

```bash
# Initialize swarm (on EC2)
docker swarm init

# Deploy your existing docker-compose
docker stack deploy -c docker-compose.yml munbon

# Scale services
docker service scale munbon_sensor-data=3

# Update service (zero-downtime)
docker service update --image subhaj888/munbon-sensor-data:v2 munbon_sensor-data
```

Benefits:
- Works with your existing docker-compose.yml
- Built into Docker (already installed)
- Rolling updates
- Health checks
- Automatic restarts
- Service discovery

This might be perfect for Munbon - simpler than Kubernetes but more powerful than plain Docker!