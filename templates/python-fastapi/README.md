# {{SERVICE_NAME}}

{{SERVICE_DESCRIPTION}}

## Prerequisites

- Python 3.11+
- Poetry (for dependency management)
- Docker (for containerization)

## Getting Started

### Development

1. Clone this repository
2. Install Poetry if you haven't already:
   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   ```

3. Install dependencies:
   ```bash
   poetry install
   ```

4. Copy environment variables:
   ```bash
   cp .env.example .env
   ```

5. Run in development mode:
   ```bash
   poetry run uvicorn app.main:app --reload
   ```

### Production

Run with Uvicorn:
```bash
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Docker

Build and run with Docker:
```bash
docker build -t {{SERVICE_NAME}} .
docker run -p 8000:8000 {{SERVICE_NAME}}
```

## API Documentation

When the service is running:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Available Commands

- `poetry run uvicorn app.main:app --reload` - Run with hot reload
- `poetry run pytest` - Run tests
- `poetry run pytest --cov` - Run tests with coverage
- `poetry run black .` - Format code
- `poetry run isort .` - Sort imports
- `poetry run flake8` - Run linter
- `poetry run mypy .` - Type checking

## Health Checks

- `/health` - Basic health check
- `/health/ready` - Readiness check (includes dependency checks)

## Metrics

Prometheus metrics are available at `/metrics`

## Project Structure

```
app/
├── api/            # API endpoints
│   └── v1/         # API version 1
├── core/           # Core functionality
├── models/         # Database models
├── schemas/        # Pydantic schemas
├── services/       # Business logic
└── main.py         # Application entry point
```

## Environment Variables

See `.env.example` for all available environment variables.

## Testing

This project uses pytest for testing.

Run tests:
```bash
poetry run pytest
```

Run with coverage:
```bash
poetry run pytest --cov=app --cov-report=html
```

## Code Quality

Format code:
```bash
poetry run black .
poetry run isort .
```

Lint code:
```bash
poetry run flake8
poetry run mypy .
```

## Deployment

### Kubernetes

Apply the Kubernetes manifests:
```bash
kubectl apply -f k8s/
```

## Contributing

1. Create a feature branch
2. Make your changes
3. Write/update tests
4. Ensure all tests pass and code is formatted
5. Submit a pull request