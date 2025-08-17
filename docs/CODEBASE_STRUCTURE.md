# Complete Codebase Structure

## Root Directory Structure
```
/munbon2-backend/
├── /services/                    # All microservices
├── /shared/                      # Shared libraries and utilities
├── /infrastructure/              # Infrastructure configurations
├── /scripts/                     # Build and deployment scripts
├── /docs/                        # Documentation
├── /tests/                       # Integration tests
├── docker-compose.yml            # Local development
├── docker-compose.prod.yml       # Production-like environment
├── .env.example                  # Environment variables template
├── .gitignore                    # Git ignore rules
├── README.md                     # Project documentation
├── CLAUDE.md                     # Claude Code guidance
├── TECHNICAL_STACK.md            # Technology decisions
├── CODEBASE_STRUCTURE.md         # This file
└── package.json                  # Root package for scripts

## Shared Libraries (/shared/)
```
/shared/
├── /typescript-common/           # Shared TypeScript utilities
│   ├── package.json
│   ├── tsconfig.json
│   ├── /src/
│   │   ├── /interfaces/         # Common interfaces
│   │   │   ├── user.interface.ts
│   │   │   ├── sensor.interface.ts
│   │   │   └── response.interface.ts
│   │   ├── /middleware/         # Common middleware
│   │   │   ├── auth.middleware.ts
│   │   │   ├── error.middleware.ts
│   │   │   ├── logging.middleware.ts
│   │   │   └── validation.middleware.ts
│   │   ├── /utils/              # Common utilities
│   │   │   ├── logger.ts
│   │   │   ├── validator.ts
│   │   │   ├── response.helper.ts
│   │   │   └── date.utils.ts
│   │   └── /constants/          # Shared constants
│   │       ├── errors.ts
│   │       ├── config.ts
│   │       └── enums.ts
│   └── /dist/                   # Compiled output
│
├── /proto/                      # Protocol Buffer definitions
│   ├── user.proto
│   ├── sensor.proto
│   ├── scada.proto
│   └── common.proto
│
└── /database-schemas/           # Shared database schemas
    ├── postgres/
    │   ├── init.sql
    │   └── migrations/
    ├── timescale/
    │   └── hypertables.sql
    └── mongodb/
        └── schemas.json

## Infrastructure (/infrastructure/)
```
/infrastructure/
├── /kubernetes/                 # K8s configurations
│   ├── /base/                   # Base configurations
│   │   ├── namespace.yaml
│   │   ├── configmap.yaml
│   │   └── secrets.yaml
│   ├── /services/               # Service-specific configs
│   │   ├── api-gateway.yaml
│   │   ├── auth-service.yaml
│   │   └── ...
│   ├── /databases/              # Database StatefulSets
│   │   ├── postgres.yaml
│   │   ├── timescaledb.yaml
│   │   ├── mongodb.yaml
│   │   ├── redis.yaml
│   │   └── influxdb.yaml
│   └── /monitoring/             # Monitoring stack
│       ├── prometheus.yaml
│       ├── grafana.yaml
│       └── jaeger.yaml
│
├── /terraform/                  # Infrastructure as Code
│   ├── main.tf
│   ├── variables.tf
│   ├── /modules/
│   └── /environments/
│
└── /helm/                       # Helm charts
    └── /munbon-backend/
        ├── Chart.yaml
        ├── values.yaml
        └── /templates/

## Node.js/TypeScript Services Structure

### API Gateway (/services/api-gateway/)
```
/services/api-gateway/
├── package.json
├── tsconfig.json
├── .env.example
├── Dockerfile
├── /src/
│   ├── index.ts                 # Entry point
│   ├── app.ts                   # Express app setup
│   ├── /config/
│   │   ├── routes.config.ts     # Route definitions
│   │   ├── services.config.ts   # Service endpoints
│   │   └── rate-limit.config.ts
│   ├── /middleware/
│   │   ├── proxy.middleware.ts
│   │   ├── auth.middleware.ts
│   │   ├── logging.middleware.ts
│   │   └── circuit-breaker.ts
│   ├── /routes/
│   │   └── health.route.ts
│   └── /utils/
│       └── service-discovery.ts
├── /tests/
│   ├── unit/
│   └── integration/
└── /dist/

### Authentication Service (/services/auth/)
```
/services/auth/
├── package.json
├── tsconfig.json
├── Dockerfile
├── /src/
│   ├── index.ts
│   ├── app.ts
│   ├── /config/
│   │   ├── database.config.ts
│   │   ├── jwt.config.ts
│   │   └── oauth.config.ts
│   ├── /controllers/
│   │   ├── auth.controller.ts
│   │   ├── user.controller.ts
│   │   └── session.controller.ts
│   ├── /services/
│   │   ├── auth.service.ts
│   │   ├── token.service.ts
│   │   ├── oauth.service.ts
│   │   └── thai-id.service.ts
│   ├── /repositories/
│   │   ├── user.repository.ts
│   │   └── session.repository.ts
│   ├── /models/
│   │   ├── user.model.ts
│   │   └── session.model.ts
│   ├── /middleware/
│   │   └── rate-limit.middleware.ts
│   ├── /routes/
│   │   ├── auth.routes.ts
│   │   └── user.routes.ts
│   └── /utils/
│       ├── password.utils.ts
│       └── token.utils.ts
├── /tests/
└── /dist/

### GIS Data Service (/services/gis/)
```
/services/gis/
├── package.json
├── tsconfig.json
├── Dockerfile
├── /src/
│   ├── index.ts
│   ├── app.ts
│   ├── /config/
│   │   ├── postgis.config.ts
│   │   └── mapbox.config.ts
│   ├── /controllers/
│   │   ├── spatial.controller.ts
│   │   ├── tiles.controller.ts
│   │   └── analysis.controller.ts
│   ├── /services/
│   │   ├── spatial.service.ts
│   │   ├── vector-tile.service.ts
│   │   ├── analysis.service.ts
│   │   └── wmts.service.ts
│   ├── /repositories/
│   │   ├── irrigation-zone.repository.ts
│   │   ├── canal.repository.ts
│   │   └── infrastructure.repository.ts
│   ├── /models/
│   │   ├── geometry.types.ts
│   │   └── spatial.models.ts
│   ├── /routes/
│   │   ├── gis.routes.ts
│   │   └── tiles.routes.ts
│   └── /utils/
│       ├── projection.utils.ts
│       └── turf.helpers.ts
├── /tests/
└── /dist/

### BFF Service (/services/bff/)
```
/services/bff/
├── package.json
├── tsconfig.json
├── Dockerfile
├── /src/
│   ├── index.ts
│   ├── app.ts
│   ├── /config/
│   │   └── graphql.config.ts
│   ├── /graphql/
│   │   ├── schema.graphql
│   │   ├── /resolvers/
│   │   │   ├── user.resolver.ts
│   │   │   ├── sensor.resolver.ts
│   │   │   ├── irrigation.resolver.ts
│   │   │   └── index.ts
│   │   ├── /types/
│   │   │   └── generated.ts
│   │   └── /dataloaders/
│   │       ├── user.loader.ts
│   │       └── sensor.loader.ts
│   ├── /services/
│   │   ├── aggregation.service.ts
│   │   └── cache.service.ts
│   └── /utils/
│       └── service-client.ts
├── /tests/
└── /dist/

## Python Services Structure

### AI Model Service (/services/ai-model/)
```
/services/ai-model/
├── pyproject.toml
├── Dockerfile
├── requirements.txt
├── .env.example
├── /src/
│   ├── __init__.py
│   ├── main.py                  # FastAPI entry
│   ├── /api/
│   │   ├── __init__.py
│   │   ├── /v1/
│   │   │   ├── predict.py
│   │   │   ├── model.py
│   │   │   └── health.py
│   │   └── dependencies.py
│   ├── /models/
│   │   ├── __init__.py
│   │   ├── spatial_temporal.py
│   │   ├── demand_forecast.py
│   │   └── optimization.py
│   ├── /services/
│   │   ├── __init__.py
│   │   ├── model_service.py
│   │   ├── preprocessing.py
│   │   └── inference.py
│   ├── /config/
│   │   ├── __init__.py
│   │   └── settings.py
│   └── /utils/
│       ├── __init__.py
│       └── tensor_utils.py
├── /models/                     # Trained models
│   ├── spatial_temporal_v1.h5
│   └── demand_forecast_v1.pkl
├── /tests/
│   ├── test_api.py
│   └── test_models.py
└── /notebooks/                  # Jupyter notebooks
    └── model_development.ipynb

### Analytics Service (/services/analytics/)
```
/services/analytics/
├── pyproject.toml
├── Dockerfile
├── /src/
│   ├── __init__.py
│   ├── main.py
│   ├── /api/
│   │   ├── __init__.py
│   │   ├── /v1/
│   │   │   ├── statistics.py
│   │   │   ├── trends.py
│   │   │   └── reports.py
│   ├── /analyzers/
│   │   ├── __init__.py
│   │   ├── water_usage.py
│   │   ├── efficiency.py
│   │   └── patterns.py
│   ├── /services/
│   │   ├── __init__.py
│   │   ├── timeseries_service.py
│   │   └── aggregation_service.py
│   └── /utils/
│       ├── __init__.py
│       ├── pandas_helpers.py
│       └── visualization.py
├── /tests/
└── /data/

## Go Services Structure

### Sensor Data Service (/services/sensor-data/)
```
/services/sensor-data/
├── go.mod
├── go.sum
├── Dockerfile
├── Makefile
├── /cmd/
│   └── server/
│       └── main.go              # Entry point
├── /internal/
│   ├── /config/
│   │   └── config.go
│   ├── /handlers/
│   │   ├── sensor.go
│   │   ├── health.go
│   │   └── websocket.go
│   ├── /services/
│   │   ├── mqtt.go
│   │   ├── timescale.go
│   │   └── validation.go
│   ├── /models/
│   │   ├── sensor.go
│   │   └── reading.go
│   ├── /repository/
│   │   ├── sensor_repo.go
│   │   └── timescale_repo.go
│   └── /middleware/
│       ├── auth.go
│       └── logging.go
├── /pkg/
│   ├── /mqtt/
│   │   └── client.go
│   └── /utils/
│       └── logger.go
└── /tests/

### SCADA Integration Service (/services/scada/)
```
/services/scada/
├── go.mod
├── go.sum
├── Dockerfile
├── /cmd/
│   └── server/
│       └── main.go
├── /internal/
│   ├── /config/
│   │   └── config.go
│   ├── /handlers/
│   │   ├── opcua.go
│   │   ├── control.go
│   │   └── stream.go
│   ├── /services/
│   │   ├── opcua_client.go
│   │   ├── data_transform.go
│   │   └── command_queue.go
│   ├── /models/
│   │   ├── scada.go
│   │   └── command.go
│   └── /adapters/
│       ├── ge_ifix.go
│       └── websocket.go
├── /pkg/
│   └── /opcua/
│       └── client.go
└── /tests/

## Java Spring Boot Service Structure

### Water Distribution Control (/services/water-control/)
```
/services/water-control/
├── build.gradle
├── settings.gradle
├── Dockerfile
├── /src/
│   ├── /main/
│   │   ├── /java/
│   │   │   └── /com/munbon/watercontrol/
│   │   │       ├── WaterControlApplication.java
│   │   │       ├── /config/
│   │   │       │   ├── DatabaseConfig.java
│   │   │       │   └── OptimizationConfig.java
│   │   │       ├── /controllers/
│   │   │       │   ├── OptimizationController.java
│   │   │       │   └── ScheduleController.java
│   │   │       ├── /services/
│   │   │       │   ├── OptimizationService.java
│   │   │       │   ├── HydraulicModelService.java
│   │   │       │   └── SchedulingService.java
│   │   │       ├── /models/
│   │   │       │   ├── Network.java
│   │   │       │   ├── Gate.java
│   │   │       │   └── OptimizationResult.java
│   │   │       ├── /repositories/
│   │   │       │   └── NetworkRepository.java
│   │   │       └── /algorithms/
│   │   │           ├── MultiObjectiveOptimizer.java
│   │   │           └── ORToolsWrapper.java
│   │   └── /resources/
│   │       ├── application.yml
│   │       └── /db/migration/
│   └── /test/
│       └── /java/
└── /gradle/

## Additional Services (Following Similar Patterns)

### Common Structure Elements:
- Each service has its own Dockerfile
- Environment configuration via .env files
- Comprehensive test coverage
- Service-specific documentation
- Health check endpoints
- Structured logging
- Error handling middleware
- OpenAPI/Swagger documentation

### Database Containers Configuration
```
/infrastructure/docker/
├── postgres/
│   ├── Dockerfile
│   └── init-scripts/
├── timescaledb/
│   ├── Dockerfile
│   └── init-scripts/
├── mongodb/
│   ├── Dockerfile
│   └── init.js
├── redis/
│   └── redis.conf
└── influxdb/
    └── config.yml
```

## Development Tools
```
/scripts/
├── setup-dev.sh                 # Initial development setup
├── generate-service.sh          # Generate new service boilerplate
├── run-tests.sh                 # Run all tests
├── build-all.sh                 # Build all services
└── deploy.sh                    # Deployment script

/docs/
├── /api/                        # API documentation
├── /architecture/               # Architecture decisions
├── /deployment/                 # Deployment guides
└── /development/                # Development guides
```