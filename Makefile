# Makefile for Munbon Backend Development

.PHONY: help up down logs build clean status setup

# Default target
help:
	@echo "Munbon Backend Development Commands"
	@echo ""
	@echo "Docker Commands:"
	@echo "  make up              - Start all databases and infrastructure"
	@echo "  make up-min          - Start only essential services (postgres, redis)"
	@echo "  make down            - Stop all services"
	@echo "  make logs            - Show logs from all services"
	@echo "  make status          - Show status of all services"
	@echo "  make clean           - Clean up volumes and containers"
	@echo ""
	@echo "Build Commands:"
	@echo "  make build           - Build all Docker images"
	@echo "  make build-service   - Build specific service (SERVICE=name)"
	@echo ""
	@echo "Kubernetes Commands:"
	@echo "  make k8s-setup       - Setup local Kubernetes"
	@echo "  make k8s-deploy      - Deploy to local Kubernetes"
	@echo "  make k8s-status      - Show Kubernetes status"
	@echo ""
	@echo "Development:"
	@echo "  make setup           - Complete local setup"
	@echo "  make test            - Run all tests"
	@echo ""

# Docker commands
up:
	@echo "Starting all services..."
	docker-compose up -d
	@echo "Services started! Waiting for health checks..."
	@sleep 5
	@make status

up-min:
	@echo "Starting minimal services (postgres, redis)..."
	docker-compose up -d postgres redis
	@echo "Minimal services started!"

down:
	@echo "Stopping all services..."
	docker-compose down
	@echo "Services stopped!"

logs:
	docker-compose logs -f

status:
	@echo "=== Service Status ==="
	@docker-compose ps
	@echo ""
	@echo "=== Database Connections ==="
	@echo "PostgreSQL:    postgresql://postgres:postgres@localhost:5432/munbon_dev"
	@echo "TimescaleDB:   postgresql://postgres:postgres@localhost:5433/munbon_timeseries"
	@echo "MongoDB:       mongodb://admin:admin@localhost:27017/munbon_dev"
	@echo "Redis:         redis://localhost:6379"
	@echo "InfluxDB:      http://localhost:8086 (admin/admin123456)"
	@echo "Kafka:         localhost:9092"
	@echo ""
	@echo "=== Management UIs ==="
	@echo "Kafka UI:      http://localhost:8090"
	@echo "Mongo Express: http://localhost:8091"
	@echo "Redis Cmdr:    http://localhost:8092"
	@echo "pgAdmin:       http://localhost:8093 (admin@munbon.local/admin)"

clean:
	@echo "Cleaning up Docker resources..."
	docker-compose down -v
	@echo "Cleanup complete!"

# Build commands
build:
	@echo "Building all services..."
	@bash scripts/docker/build-all.sh

build-service:
	@if [ -z "$(SERVICE)" ]; then \
		echo "Please specify SERVICE=<service-name>"; \
		exit 1; \
	fi
	@echo "Building $(SERVICE)..."
	@bash scripts/docker/build-all.sh --service $(SERVICE)

# Kubernetes commands
k8s-setup:
	@echo "Setting up local Kubernetes..."
	@cd infrastructure/kubernetes && make setup

k8s-deploy:
	@echo "Deploying to local Kubernetes..."
	@cd infrastructure/kubernetes && make deploy-local

k8s-status:
	@cd infrastructure/kubernetes && make status

# Complete setup
setup: up k8s-setup
	@echo ""
	@echo "=== Setup Complete! ==="
	@echo ""
	@echo "1. Databases are running (docker-compose)"
	@echo "2. Kubernetes is configured"
	@echo ""
	@echo "Next steps:"
	@echo "  - Create services from templates: cd templates && ./init-service.sh <language> <service-name>"
	@echo "  - Build services: make build"
	@echo "  - Deploy to K8s: make k8s-deploy"
	@echo ""
	@echo "Happy coding! 🚀"

# Registry management
registry-start:
	@docker run -d -p 5000:5000 --restart=always --name registry registry:2 || echo "Registry already running"

registry-stop:
	@docker stop registry && docker rm registry || echo "Registry not running"

registry-list:
	@echo "Images in local registry:"
	@curl -s http://localhost:5000/v2/_catalog | jq '.repositories[]' || echo "Registry not accessible"

# Database initialization scripts
db-init:
	@echo "Initializing databases..."
	@docker-compose exec postgres psql -U postgres -d munbon_dev -f /docker-entrypoint-initdb.d/init.sql || true
	@docker-compose exec timescaledb psql -U postgres -d munbon_timeseries -f /docker-entrypoint-initdb.d/init.sql || true
	@echo "Databases initialized!"

# Port forwarding helpers
port-api:
	kubectl port-forward -n munbon svc/api-gateway 3000:3000

port-grafana:
	kubectl port-forward -n munbon-monitoring svc/grafana 3001:80

# Test commands
test:
	@echo "Running tests..."
	@for dir in services/*/*; do \
		if [ -f "$$dir/package.json" ]; then \
			echo "Testing $$dir..."; \
			cd "$$dir" && npm test || true; \
			cd -; \
		fi \
	done