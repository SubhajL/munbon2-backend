# {{SERVICE_NAME}} Service

A Go microservice built for the Munbon Irrigation Backend system.

## Structure

```
.
├── cmd/
│   └── server/
│       └── main.go         # Application entry point
├── internal/
│   ├── config/            # Configuration management
│   ├── handlers/          # HTTP handlers
│   └── middleware/        # HTTP middleware
├── pkg/                   # Public packages
├── deployments/
│   └── k8s/              # Kubernetes manifests
├── go.mod                # Go module definition
├── go.sum                # Go module checksums
├── Dockerfile            # Container definition
└── README.md            # This file
```

## Development

### Prerequisites

- Go 1.21 or higher
- Docker (for containerization)
- Make (optional, for Makefile commands)

### Running Locally

```bash
# Install dependencies
go mod download

# Run the service
go run cmd/server/main.go

# Or with environment variables
PORT=8080 go run cmd/server/main.go
```

### Building

```bash
# Build binary
go build -o bin/server cmd/server/main.go

# Build Docker image
docker build -t {{SERVICE_NAME}}:latest .
```

### Testing

```bash
# Run tests
go test ./...

# Run tests with coverage
go test -cover ./...
```

## Configuration

The service is configured via environment variables:

- `PORT`: HTTP server port (default: 8080)
- `LOG_LEVEL`: Logging level (default: info)
- `ENVIRONMENT`: Environment name (default: development)

## API Endpoints

- `GET /health` - Health check endpoint
- `GET /ready` - Readiness check endpoint
- `GET /metrics` - Prometheus metrics endpoint

## Deployment

The service includes Kubernetes manifests in the `deployments/k8s` directory:

```bash
# Deploy to Kubernetes
kubectl apply -f deployments/k8s/
```

## Docker

### Building the image

```bash
docker build -t munbon/{{SERVICE_NAME}}:latest .
```

### Running the container

```bash
docker run -p 8080:8080 munbon/{{SERVICE_NAME}}:latest
```

## Development Guidelines

1. Follow standard Go project layout
2. Use structured logging
3. Handle errors explicitly
4. Write tests for all business logic
5. Use interfaces for dependencies
6. Keep handlers thin - business logic in services
7. Use context for request-scoped values