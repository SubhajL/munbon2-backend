# Makefile for Kubernetes infrastructure management

.PHONY: help setup deploy-local clean status logs

# Default target
help:
	@echo "Munbon Kubernetes Infrastructure Management"
	@echo ""
	@echo "Available targets:"
	@echo "  setup         - Setup local Kubernetes environment"
	@echo "  deploy-local  - Deploy to local Kubernetes"
	@echo "  clean         - Clean up Kubernetes resources"
	@echo "  status        - Show cluster status"
	@echo "  logs          - Show logs from all pods"
	@echo ""
	@echo "Usage: make <target>"

# Setup local environment
setup:
	@echo "Setting up local Kubernetes environment..."
	@bash scripts/setup-local.sh

# Deploy to local cluster
deploy-local:
	@echo "Deploying to local Kubernetes cluster..."
	kubectl apply -k overlays/local
	@echo "Deployment complete!"

# Clean up resources
clean:
	@echo "Cleaning up Kubernetes resources..."
	kubectl delete -k overlays/local || true
	@echo "Cleanup complete!"

# Show cluster status
status:
	@echo "=== Cluster Info ==="
	@kubectl cluster-info
	@echo "\n=== Nodes ==="
	@kubectl get nodes
	@echo "\n=== Namespaces ==="
	@kubectl get namespaces | grep munbon
	@echo "\n=== Pods in munbon namespace ==="
	@kubectl get pods -n munbon
	@echo "\n=== Services in munbon namespace ==="
	@kubectl get svc -n munbon

# Show logs from all pods
logs:
	@echo "Showing logs from all pods in munbon namespace..."
	@kubectl logs -n munbon -l environment=local --all-containers=true --tail=50

# Port forwarding shortcuts
port-forward-api:
	kubectl port-forward -n munbon svc/api-gateway 3000:3000

port-forward-grafana:
	kubectl port-forward -n munbon-monitoring svc/grafana 3001:80

# Registry helpers
registry-start:
	@docker run -d -p 5000:5000 --restart=always --name registry registry:2 || echo "Registry already running"

registry-stop:
	@docker stop registry && docker rm registry || echo "Registry not running"

# Helm helpers
helm-deps:
	@helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
	@helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
	@helm repo add grafana https://grafana.github.io/helm-charts
	@helm repo update

helm-install-local:
	@helm install munbon ./charts/munbon -f ./charts/munbon/values-local.yaml --namespace munbon

helm-upgrade-local:
	@helm upgrade munbon ./charts/munbon -f ./charts/munbon/values-local.yaml --namespace munbon

helm-uninstall:
	@helm uninstall munbon --namespace munbon || true