# Technical Stack Specifications

## Language Selection Rationale

### Node.js with TypeScript (Primary Stack)
**Why:** 
- Excellent for I/O-intensive operations (API calls, database queries)
- Large ecosystem of packages for web services
- TypeScript provides type safety and better maintainability
- Same language across multiple services reduces context switching
- Great for real-time features with WebSocket support

**Framework Choices:**
- **Express.js**: For simple REST APIs
- **Fastify**: For high-performance APIs (3x faster than Express)
- **NestJS**: For enterprise-grade services with dependency injection

### Python with FastAPI
**Why:**
- Best-in-class AI/ML libraries (TensorFlow, PyTorch, Scikit-learn)
- Excellent data manipulation with Pandas/NumPy
- FastAPI provides async support and automatic OpenAPI docs
- Native support for scientific computing

**Use Cases:**
- Machine learning model serving
- Data analysis and ETL pipelines
- Integration with scientific models (AquaCrop)

### Go
**Why:**
- Exceptional performance for high-throughput services
- Built-in concurrency with goroutines
- Small memory footprint and fast startup
- Excellent for network programming (OPC UA)
- Native compilation produces small binaries

**Use Cases:**
- Services handling millions of sensor readings
- Real-time SCADA communication
- System monitoring with minimal overhead

### Java Spring Boot
**Why:**
- Mature ecosystem for complex business logic
- Excellent integration with optimization libraries (OR-Tools)
- Strong typing and enterprise patterns
- Robust error handling and transaction management

**Use Cases:**
- Complex water distribution algorithms
- Business rule engines
- Integration with enterprise systems

## Service-Specific Technology Stack

### 1. API Gateway (Node.js/TypeScript)
```typescript
- Framework: Express + http-proxy-middleware
- Libraries: 
  - express-rate-limit (rate limiting)
  - helmet (security headers)
  - morgan (logging)
  - joi (validation)
```

### 2. Authentication Service (Node.js/TypeScript)
```typescript
- Framework: Express
- Libraries:
  - passport (authentication strategies)
  - jsonwebtoken (JWT)
  - bcrypt (password hashing)
  - speakeasy (2FA)
  - ioredis (session management)
```

### 3. GIS Data Service (Node.js/TypeScript)
```typescript
- Framework: Fastify (performance)
- Libraries:
  - @turf/turf (spatial operations)
  - node-postgres (PostGIS queries)
  - mapbox-gl (vector tiles)
  - proj4 (coordinate transformations)
```

### 4. Sensor Data Service (Go)
```go
- Framework: Gin or Fiber
- Libraries:
  - eclipse/paho.mqtt.golang (MQTT client)
  - influxdata/influxdb-client-go
  - gorilla/websocket
  - uber-go/zap (logging)
```

### 5. SCADA Integration Service (Go)
```go
- Framework: Native Go
- Libraries:
  - gopcua/opcua (OPC UA client)
  - gorilla/websocket (real-time)
  - golang/protobuf (data serialization)
```

### 6. AI Model Service (Python/FastAPI)
```python
- Framework: FastAPI
- Libraries:
  - tensorflow-serving-api
  - torch (PyTorch)
  - numpy, pandas
  - celery (background tasks)
  - mlflow (model management)
```

### 7. Water Distribution Control (Java Spring Boot)
```java
- Framework: Spring Boot 3.x
- Libraries:
  - OR-Tools (optimization)
  - Apache Commons Math
  - Spring Data JPA
  - Spring Batch (bulk operations)
```

## Shared Libraries and Standards

### Cross-Service Communication
- **gRPC**: For internal service communication (optional)
- **REST**: For external APIs
- **Apache Kafka**: For event streaming
- **Protocol Buffers**: For data serialization

### Observability Stack
- **OpenTelemetry**: Distributed tracing
- **Prometheus**: Metrics collection
- **Grafana**: Visualization
- **ELK Stack**: Centralized logging

### Development Standards
```yaml
Node.js Services:
  - Node version: 20 LTS
  - TypeScript: 5.x
  - Linting: ESLint + Prettier
  - Testing: Jest + Supertest
  - Package manager: npm

Python Services:
  - Python version: 3.11+
  - Type hints: Required
  - Linting: Black + Flake8 + mypy
  - Testing: pytest
  - Package manager: Poetry

Go Services:
  - Go version: 1.21+
  - Module system: Go modules
  - Linting: golangci-lint
  - Testing: Built-in + testify

Java Services:
  - Java version: 17 LTS
  - Build tool: Gradle
  - Testing: JUnit 5 + Mockito
```

## Container Specifications

### Base Images
```dockerfile
# Node.js services
FROM node:20-alpine

# Python services  
FROM python:3.11-slim

# Go services
FROM golang:1.21-alpine AS builder
FROM alpine:latest (runtime)

# Java services
FROM eclipse-temurin:17-jre-alpine
```

### Resource Limits (Kubernetes)
```yaml
Node.js Services:
  requests: { memory: "256Mi", cpu: "100m" }
  limits: { memory: "512Mi", cpu: "500m" }

Python Services:
  requests: { memory: "512Mi", cpu: "200m" }
  limits: { memory: "1Gi", cpu: "1000m" }

Go Services:
  requests: { memory: "128Mi", cpu: "100m" }
  limits: { memory: "256Mi", cpu: "500m" }

Java Services:
  requests: { memory: "512Mi", cpu: "200m" }
  limits: { memory: "2Gi", cpu: "1000m" }
```