# Munbon Backend Service Ports Documentation

This document lists all the localhost ports used by different services in the Munbon backend project for local development.

## Database Services

| Service | Container Name | Internal Port | External Port | Description |
|---------|---------------|---------------|---------------|-------------|
| PostgreSQL + PostGIS | munbon-postgres | 5432 | 5432 | Main relational database with spatial support |
| TimescaleDB | munbon-timescaledb | 5432 | 5433 | Time-series database for sensor data |
| MongoDB | munbon-mongodb | 27017 | 27017 | Document database |
| Redis | munbon-redis | 6379 | 6379 | Caching and session management |
| InfluxDB | munbon-influxdb | 8086 | 8086 | Metrics database |

## Message Queue Services

| Service | Container Name | Internal Port | External Port | Description |
|---------|---------------|---------------|---------------|-------------|
| Apache Kafka | munbon-kafka | 29092 (internal) | 9092 | Event streaming platform |
| Zookeeper | munbon-zookeeper | 2181 | 2181 | Kafka coordination service |

## Development Tools

| Service | Container Name | Internal Port | External Port | Description |
|---------|---------------|---------------|---------------|-------------|
| Kafka UI | munbon-kafka-ui | 8080 | 8090 | Web interface for Kafka |
| MongoDB Express | munbon-mongo-express | 8081 | 8091 | Web interface for MongoDB |
| Redis Commander | munbon-redis-commander | 8081 | 8092 | Web interface for Redis |
| pgAdmin | munbon-pgadmin | 80 | 8093 | Web interface for PostgreSQL |

## Core Microservices

Based on the docker-compose configuration and project documentation, the following ports are reserved for microservices:

| Service | Port | Language/Framework | Description |
|---------|------|--------------------|-------------|
| API Gateway | 3000 | Node.js/TypeScript | Main entry point for external API requests |
| Authentication Service | 8001 | Node.js/TypeScript | OAuth 2.0, JWT authentication |

### Planned Service Ports (Not Yet Implemented)

The following ports are suggested for services that haven't been implemented yet:

#### Node.js/TypeScript Services
| Service | Suggested Port | Description |
|---------|----------------|-------------|
| GIS Data Service | 8002 | PostGIS spatial operations, vector tiles |
| User Management Service | 8003 | User profiles, roles, permissions |
| Weather Integration Service | 8004 | Thai Meteorological Department API |
| Notification Service | 8005 | Multi-channel alerts (Email, LINE, SMS) |
| Alert Management Service | 8006 | Alert rules engine |
| Configuration Service | 8007 | Centralized config management |
| BFF Service | 8008 | GraphQL Backend for Frontend |
| WebSocket Service | 8009 | Real-time communication |
| Reporting Service | 8010 | PDF report generation |
| File Processing Service | 8011 | Large file handling |
| Maintenance Service | 8012 | Equipment maintenance tracking |

#### Python/FastAPI Services
| Service | Suggested Port | Description |
|---------|----------------|-------------|
| AI Model Service | 8100 | TensorFlow/PyTorch model serving |
| Analytics Service | 8101 | Data analysis with Pandas/NumPy |
| Data Integration Service | 8102 | ETL pipelines |
| Crop Management Service | 8103 | AquaCrop model integration |

#### Go Services
| Service | Suggested Port | Description |
|---------|----------------|-------------|
| Sensor Data Service | 8200 | High-throughput MQTT data ingestion |
| SCADA Integration Service | 8201 | GE iFix OPC UA communication |
| System Monitoring Service | 8202 | Prometheus metrics, health checks |

#### Java Spring Boot Services
| Service | Suggested Port | Description |
|---------|----------------|-------------|
| Water Distribution Control Service | 8300 | Multi-objective optimization algorithms |

## Additional Ports

| Service | Port | Description |
|---------|------|-------------|
| MQTT Broker (for Sensor Data) | 1883 | MQTT protocol for IoT devices |
| MQTT WebSocket | 9001 | MQTT over WebSocket |
| Prometheus | 9090 | Metrics collection |
| Grafana | 3001 | Metrics visualization |

## Port Range Summary

- **3000-3999**: Frontend and gateway services
- **5000-5999**: Database services
- **6000-6999**: Cache and session services
- **8000-8099**: Core Node.js microservices
- **8100-8199**: Python microservices
- **8200-8299**: Go microservices
- **8300-8399**: Java microservices
- **8090-8099**: Development tools
- **9000-9999**: Message queue and monitoring services

## Usage

To start all infrastructure services:
```bash
docker-compose up -d
```

To start with development tools:
```bash
docker-compose --profile tools up -d
```

To start specific services:
```bash
docker-compose up -d postgres redis kafka
```

## Notes

1. All services are configured to run on the `munbon-network` Docker network for internal communication.
2. Services can communicate internally using container names (e.g., `postgres:5432` instead of `localhost:5432`).
3. Resource limits are set for each container to optimize performance on development machines.
4. The `docker-compose.override.yml` file enables all development tools by default.