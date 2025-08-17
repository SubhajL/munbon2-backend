# Munbon Microservice Templates

This directory contains boilerplate templates for quickly scaffolding new microservices in different programming languages for the Munbon Irrigation Backend project.

## Available Templates

1. **nodejs-typescript** - Node.js with TypeScript, Express.js framework
2. **python-fastapi** - Python with FastAPI framework
3. **go** - Go with standard library HTTP server
4. **java-springboot** - Java with Spring Boot framework

## Features

Each template includes:

- ✅ Standard directory structure following language best practices
- ✅ Dockerfile with multi-stage builds
- ✅ Kubernetes manifests (deployment, service)
- ✅ Health check and readiness endpoints
- ✅ Configuration management
- ✅ Logging setup
- ✅ Error handling
- ✅ API documentation (Swagger/OpenAPI)
- ✅ Basic test structure
- ✅ Security middleware
- ✅ Prometheus metrics endpoint

## Usage

### Using the Initialization Script (Recommended)

```bash
cd templates
./init-service.sh <language> <service-name> [target-directory]
```

Examples:
```bash
# Create a Node.js/TypeScript service
./init-service.sh nodejs-typescript sensor-data-service

# Create a Python/FastAPI service in a specific directory
./init-service.sh python-fastapi ml-prediction-service ../services/ml-prediction

# Create a Go service
./init-service.sh go scada-integration-service

# Create a Java/Spring Boot service
./init-service.sh java-springboot water-allocation-service
```

The script will:
1. Copy the template to the target directory
2. Replace all placeholders with your service name
3. Initialize a git repository
4. Install dependencies (if the required tools are available)
5. Provide next steps for development

### Manual Usage

1. Copy the desired template directory:
```bash
cp -r nodejs-typescript ../services/my-new-service
```

2. Replace placeholders in all files:
- `{{SERVICE_NAME}}` - Replace with your service name (lowercase)
- `{{SERVICE_NAME_UPPER}}` - Replace with uppercase version
- `{{SERVICE_NAME_CAMEL}}` - Replace with CamelCase version

3. For Java services, rename package directories:
```bash
mv src/main/java/com/munbon/{{SERVICE_NAME}} src/main/java/com/munbon/myservice
```

4. Initialize git and install dependencies

## Template Structure

### Node.js/TypeScript Template
```
nodejs-typescript/
├── src/
│   ├── config/
│   ├── controllers/
│   ├── middleware/
│   ├── routes/
│   ├── services/
│   ├── types/
│   ├── utils/
│   └── app.ts
├── tests/
├── deployments/k8s/
├── package.json
├── tsconfig.json
├── Dockerfile
└── README.md
```

### Python/FastAPI Template
```
python-fastapi/
├── app/
│   ├── api/
│   ├── core/
│   ├── models/
│   ├── services/
│   └── main.py
├── tests/
├── deployments/k8s/
├── pyproject.toml
├── Dockerfile
└── README.md
```

### Go Template
```
go/
├── cmd/server/
├── internal/
│   ├── config/
│   ├── handlers/
│   └── middleware/
├── pkg/
├── deployments/k8s/
├── go.mod
├── Dockerfile
└── README.md
```

### Java/Spring Boot Template
```
java-springboot/
├── src/
│   ├── main/
│   │   ├── java/com/munbon/{{SERVICE_NAME}}/
│   │   └── resources/
│   └── test/
├── deployments/k8s/
├── pom.xml
├── Dockerfile
└── README.md
```

## Customization

After creating a service from a template, you should:

1. Update the README with service-specific information
2. Modify the API endpoints to match your service requirements
3. Add database connections if needed
4. Configure external service integrations
5. Update Kubernetes resource limits based on expected load
6. Add service-specific environment variables
7. Implement proper authentication/authorization
8. Add comprehensive tests

## Best Practices

1. **Naming Convention**: Use kebab-case for service names (e.g., `sensor-data-service`)
2. **Port Assignment**: Ensure each service uses a unique port in development
3. **Configuration**: Use environment variables for all configuration
4. **Security**: Never commit secrets or credentials
5. **Testing**: Write tests for all business logic
6. **Documentation**: Keep README and API docs up to date
7. **Versioning**: Use semantic versioning for your services

## Language-Specific Notes

### Node.js/TypeScript
- Uses npm for package management
- Includes ESLint and Prettier configurations
- TypeScript strict mode enabled
- Jest for testing

### Python/FastAPI
- Uses Poetry for dependency management
- Includes pytest configuration
- Type hints throughout
- Async/await support

### Go
- Follows standard Go project layout
- Uses Go modules
- Includes graceful shutdown
- Context-aware handlers

### Java/Spring Boot
- Uses Maven for build management
- Spring Boot 3.x with Java 17
- Includes Actuator for monitoring
- JUnit 5 for testing

## Troubleshooting

### Common Issues

1. **Port conflicts**: Make sure the port specified in configuration is not already in use
2. **Missing dependencies**: Ensure language runtime is installed (Node.js, Python, Go, Java)
3. **Docker build fails**: Check that Docker daemon is running
4. **Template not found**: Ensure you're running the script from the templates directory

### Getting Help

If you encounter issues:
1. Check the language-specific README in the created service
2. Review the error messages carefully
3. Ensure all prerequisites are installed
4. Check the project documentation