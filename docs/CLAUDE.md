# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
Munbon Irrigation Control System Backend - A microservice-based solution for automated water control and management in Thailand's Munbon Irrigation Project.

## Current Project Status
- **Phase**: Initial setup - no code implemented yet
- **Tasks**: 36 tasks defined via TaskMaster (0% complete)
- **Architecture**: Microservice with BFF pattern planned

## System Architecture

### Core Microservices (10 services)
1. **Authentication & Authorization Service** - OAuth 2.0, Thai Digital ID, JWT
2. **GIS Data Service** - PostGIS spatial operations, vector tiles
3. **SCADA Integration Service** - GE iFix OPC UA communication
4. **AI Model Service** - TensorFlow serving, model versioning
5. **Sensor Data Service** - MQTT, time-series data ingestion
6. **Water Distribution Control Service** - Multi-objective optimization
7. **User Management Service** - User profiles, roles, permissions
8. **Weather Integration Service** - Thai Meteorological Department API
9. **Crop Management Service** - AquaCrop model integration
10. **Scheduling Service** - Irrigation/maintenance scheduling

### Supporting Services
- **BFF Service** - Frontend aggregation layer with GraphQL
- **Notification Service** - Multi-channel alerts
- **Alert Management Service** - Alert rules engine
- **Configuration Service** - Centralized config management
- **Analytics Service** - Data analysis and insights
- **Maintenance Service** - Equipment maintenance tracking
- **Data Integration Service** - ETL operations
- **File Processing Service** - Large file handling
- **Reporting Service** - Report generation
- **System Monitoring Service** - Health checks, metrics

## Technology Stack

### Databases (Each in separate container)
- **PostgreSQL + PostGIS** (port 5432) - Spatial data
- **TimescaleDB** (port 5433) - Time-series sensor data
- **MongoDB** (port 27017) - Document storage
- **Redis** (port 6379) - Caching and sessions
- **InfluxDB** (port 8086) - Metrics

### Infrastructure
- **Container Orchestration**: Kubernetes
- **API Gateway**: Kong or Traefik
- **Message Broker**: Apache Kafka
- **Container Runtime**: Docker

### Programming Languages by Service

#### Node.js with TypeScript (13 services)
- API Gateway - Express/Fastify
- Authentication & Authorization Service - Passport.js, JWT
- GIS Data Service - PostGIS queries, Turf.js
- User Management Service - CRUD operations
- Weather Integration Service - External API calls
- Notification Service - Multi-channel messaging
- Alert Management Service - Event-driven alerts
- Configuration Service - Dynamic config management
- BFF Service - GraphQL with Apollo Server
- WebSocket Service - Socket.IO real-time
- Reporting Service - PDF generation
- File Processing Service - Stream processing
- Maintenance Service - CRUD with scheduling

#### Python with FastAPI (4 services)
- AI Model Service - TensorFlow/PyTorch serving
- Analytics Service - Pandas, NumPy analysis
- Data Integration Service - ETL pipelines
- Crop Management Service - AquaCrop integration

#### Go (3 services)
- Sensor Data Service - High-throughput ingestion
- SCADA Integration Service - OPC UA client
- System Monitoring Service - Prometheus metrics

#### Java Spring Boot (1 service)
- Water Distribution Control Service - Complex optimization algorithms

## TaskMaster Integration
This project uses TaskMaster via MCP. To interact with tasks:
- View tasks: "Show me all tasks" or "List pending tasks"
- Get next task: "What's the next task?"
- Update status: "Mark task X as in-progress/done"
- View details: "Show me task X"
- Expand tasks: "Expand task X into subtasks"

## Key Integration Points
1. **SCADA**: GE iFix via OPC UA protocol
2. **Thai Government**: OAuth 2.0 with Thai Digital ID
3. **Weather**: Thai Meteorological Department API
4. **Agriculture**: FAO AquaCrop model
5. **Messaging**: LINE integration for notifications

## Development Workflow
1. Check available tasks using TaskMaster
2. Tasks are ordered by dependencies
3. Start with infrastructure tasks (1-3)
4. Database setup tasks (5, 7, 11, 14, 16, 36)
5. Implement core services following dependencies
6. Each service should be in its own directory under `/services/`
7. Use Docker Compose for local development
8. Deploy to Kubernetes for production

## Project Structure (Planned)
```
/munbon2-backend/
├── /services/           # Microservices
│   ├── /auth/          # Authentication service
│   ├── /gis/           # GIS data service
│   ├── /scada/         # SCADA integration
│   └── ...             # Other services
├── /shared/            # Shared libraries
├── /k8s/               # Kubernetes manifests
├── docker-compose.yml  # Local development
└── /tasks/             # TaskMaster tasks
```

## Important Constraints
- Must support 10,000+ concurrent connections
- Sub-second API response times required
- 99.9% uptime SLA
- Thai government security compliance required
- Limited sensor infrastructure (mobile sensors, no flow meters at most gates)

## Programming Principles
- Read, Understand, and Follows PROGRAMMING_PRINCIPLES for specific languages: 