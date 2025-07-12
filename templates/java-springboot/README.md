# {{SERVICE_NAME}} Service

A Spring Boot microservice built for the Munbon Irrigation Backend system.

## Structure

```
.
├── src/
│   ├── main/
│   │   ├── java/com/munbon/{{SERVICE_NAME}}/
│   │   │   ├── config/           # Configuration classes
│   │   │   ├── controller/       # REST controllers
│   │   │   ├── service/         # Business logic
│   │   │   ├── repository/      # Data access layer
│   │   │   ├── dto/            # Data transfer objects
│   │   │   ├── entity/         # JPA entities
│   │   │   ├── exception/      # Custom exceptions
│   │   │   └── Application.java # Main application class
│   │   └── resources/
│   │       ├── application.yml  # Main configuration
│   │       ├── application-dev.yml
│   │       └── application-prod.yml
│   └── test/                    # Test classes
├── deployments/
│   └── k8s/                    # Kubernetes manifests
├── pom.xml                     # Maven configuration
├── Dockerfile                  # Container definition
└── README.md                   # This file
```

## Development

### Prerequisites

- Java 17 or higher
- Maven 3.8 or higher
- Docker (for containerization)

### Running Locally

```bash
# Run with Maven
mvn spring-boot:run

# Or build and run JAR
mvn clean package
java -jar target/{{SERVICE_NAME}}-1.0.0.jar

# Run with specific profile
java -jar target/{{SERVICE_NAME}}-1.0.0.jar --spring.profiles.active=dev
```

### Building

```bash
# Build JAR
mvn clean package

# Build Docker image
docker build -t {{SERVICE_NAME}}:latest .
```

### Testing

```bash
# Run all tests
mvn test

# Run tests with coverage
mvn test jacoco:report

# Run specific test class
mvn test -Dtest=HealthControllerTest
```

## Configuration

The service uses Spring Boot's configuration management with profiles:

- `application.yml` - Default configuration
- `application-dev.yml` - Development profile
- `application-prod.yml` - Production profile

Key configuration properties:
- `server.port`: HTTP server port (default: 8080)
- `logging.level`: Log levels
- `management.endpoints`: Actuator endpoints configuration

## API Documentation

When running, the API documentation is available at:
- Swagger UI: http://localhost:8080/swagger-ui.html
- OpenAPI JSON: http://localhost:8080/v3/api-docs

## Endpoints

### Application Endpoints
- `GET /health` - Health check endpoint
- `GET /health/ready` - Readiness check endpoint

### Actuator Endpoints
- `GET /actuator/health` - Detailed health information
- `GET /actuator/info` - Application information
- `GET /actuator/metrics` - Application metrics
- `GET /actuator/prometheus` - Prometheus metrics

## Deployment

### Docker

```bash
# Build image
docker build -t munbon/{{SERVICE_NAME}}:latest .

# Run container
docker run -p 8080:8080 -e SPRING_PROFILES_ACTIVE=prod munbon/{{SERVICE_NAME}}:latest
```

### Kubernetes

```bash
# Deploy to Kubernetes
kubectl apply -f deployments/k8s/
```

## Development Guidelines

1. Follow standard Spring Boot project structure
2. Use constructor injection for dependencies
3. Separate concerns: Controller → Service → Repository
4. Use DTOs for API contracts
5. Implement proper exception handling
6. Write unit and integration tests
7. Use Spring profiles for environment configuration
8. Follow RESTful API design principles
9. Document APIs using OpenAPI annotations
10. Use SLF4J for logging