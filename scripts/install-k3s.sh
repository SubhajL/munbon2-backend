#!/bin/bash
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}=== Installing K3s on EC2 Instance ===${NC}"

# Check if running as root or with sudo
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}This script must be run as root or with sudo${NC}"
   exit 1
fi

# System preparation
echo -e "${YELLOW}Preparing system...${NC}"
apt-get update
apt-get install -y curl wget

# Install K3s with specific configuration
echo -e "${YELLOW}Installing K3s...${NC}"
curl -sfL https://get.k3s.io | sh -s - \
    --write-kubeconfig-mode 644 \
    --disable traefik \
    --node-name munbon-master

# Wait for K3s to be ready
echo -e "${YELLOW}Waiting for K3s to be ready...${NC}"
sleep 10
kubectl wait --for=condition=Ready node/munbon-master --timeout=60s

# Install Traefik 2 as ingress controller
echo -e "${YELLOW}Installing Traefik 2...${NC}"
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Namespace
metadata:
  name: traefik
---
apiVersion: helm.cattle.io/v1
kind: HelmChart
metadata:
  name: traefik
  namespace: kube-system
spec:
  repo: https://helm.traefik.io/traefik
  chart: traefik
  targetNamespace: traefik
  createNamespace: true
  valuesContent: |-
    deployment:
      replicas: 1
    service:
      type: LoadBalancer
    ports:
      web:
        redirectTo: websecure
      websecure:
        tls:
          enabled: true
    ingressRoute:
      dashboard:
        enabled: false
    resources:
      requests:
        cpu: 100m
        memory: 128Mi
      limits:
        cpu: 300m
        memory: 256Mi
EOF

# Install cert-manager for SSL certificates
echo -e "${YELLOW}Installing cert-manager...${NC}"
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.2/cert-manager.yaml

# Create namespace for munbon services
echo -e "${YELLOW}Creating munbon namespace...${NC}"
kubectl create namespace munbon || true

# Install local-path storage provisioner
echo -e "${YELLOW}Installing local-path storage provisioner...${NC}"
kubectl apply -f https://raw.githubusercontent.com/rancher/local-path-provisioner/v0.0.26/deploy/local-path-storage.yaml
kubectl patch storageclass local-path -p '{"metadata": {"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}'

# Create kubeconfig for external access
echo -e "${YELLOW}Configuring external access...${NC}"
EXTERNAL_IP="43.209.22.250"
cp /etc/rancher/k3s/k3s.yaml /root/k3s-kubeconfig.yaml
sed -i "s/127.0.0.1/${EXTERNAL_IP}/g" /root/k3s-kubeconfig.yaml

# Display cluster info
echo -e "${GREEN}K3s installation complete!${NC}"
echo -e "${YELLOW}Cluster nodes:${NC}"
kubectl get nodes
echo -e "${YELLOW}All pods:${NC}"
kubectl get pods --all-namespaces

echo -e "${GREEN}=== Installation Summary ===${NC}"
echo "K3s version: $(k3s --version | head -n1)"
echo "Kubeconfig: /root/k3s-kubeconfig.yaml"
echo "External access: export KUBECONFIG=/root/k3s-kubeconfig.yaml"
echo ""
echo -e "${YELLOW}To access from local machine:${NC}"
echo "scp ubuntu@${EXTERNAL_IP}:/root/k3s-kubeconfig.yaml ~/.kube/munbon-k3s.yaml"
echo "export KUBECONFIG=~/.kube/munbon-k3s.yaml"