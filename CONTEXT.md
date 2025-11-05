# Munbon2 Backend – Architectural Context

## 0. Irrigation Canal Worktree

### nIrrigation Canal Worktree (Canal planning & delivery)
Category	Details
Primary services	services/bff-water-planning (GraphQL, schedulers), services/flow-monitoring (hydraulics, Kafka), services/ros-gis-integration (ROS↔GIS bridge), services/scheduler (weekly ops), services/awd-control (for canal valves), services/gis, services/water-accounting, services/gravity-optimizer (if active).
Data sources	Timescale sensor_data (water levels, shared), Postgres munbon_dev (ros.*, scheduler tables), PostGIS gis, SCADA MSSQL (tb_gatelevel_command), Redis, Kafka.
Key tables	ros.daily_demands, ros.weekly_demands, ros_hydraulics.*; gis.hydraulic_network, gis.sensor_data; sensor_management.sensor_mappings; scheduler.weekly_schedules, .scheduled_operations; AWD tables awd.*; InfluxDB buckets for flow analytics.
Focus directories	services/bff-water-planning/src (services, schedulers, tests), services/flow-monitoring/src, services/ros-gis-integration/src, services/scheduler/src, services/awd-control/src, services/gis/src, services/water-accounting/src.
Explicit exclusions	All smart-farm specific services (services/smartfarm-water-control, services/bff-water-control, services/moisture-monitoring, services/weather-monitoring except read-only for shared APIs), frontends outside canal domain.
Integration coordination	Any changes to shared DB schemas (sensor_data, munbon_dev, sensor_management), Kafka topics, or AWD interfaces must be communicated to smart-farm worktree. Ensure valve commands and sensor mappings remain compatible with smart-farm usage.

### Prompt template for Irrigation Canal AI instance

You are working exclusively on the irrigation canal planning and delivery stack. Focus on:

services/bff-water-planning, services/flow-monitoring, services/ros-gis-integration, services/scheduler, services/awd-control, services/gis, services/water-accounting, services/gravity-optimizer
Relevant docs (CONTEXT.md, CLAUDE.md, docs/CLAUDE_INSTANCE_*)
Do not modify smart-farm services (services/smartfarm-water-control, services/bff-water-control, services/moisture-monitoring, services/weather-monitoring); read them only for shared configuration references.
Datastores: Timescale sensor_data, Postgres/PostGIS munbon_dev & gis, SCADA MSSQL. Coordinate schema/API changes with the smart-farm worktree to keep sensor mappings and AWD command interfaces consistent.

### Coordination checklist for both worktrees

Share any migrations touching sensor_data, munbon_dev, gis, or sensor_management schemas.
Notify counterpart if you change Kafka topic names, Redis keys, SQS queue processing, or AWD command payloads.
Keep shared documentation (CONTEXT.md, docs/CLAUDE_INSTANCE_*) updated with changes affecting both domains.
If introducing new APIs or changing existing ones between services (e.g., ROS/GIS endpoints, sensor-data APIs), announce and document the contract.

## 1. System Overview
- Mission: automate water planning, distribution, and monitoring for the Munbon Irrigation Project in Thailand.
- Approach: microservice ecosystem (Node.js/TypeScript, Go, Python/FastAPI, Java/Spring) orchestrated via Docker/Kubernetes, fronted by Kong API Gateway and multiple BFFs (web, mobile, water planning/control).
- External stakeholders: field IoT sensors, GE iFix SCADA, Royal Irrigation Department data, Thai Meteorological Department (TMD), Aeronautical Weather Stations (AOS), ROS runoff services.

## 2. Layered Architecture (ref. `docs/SYSTEM_E2E_FLOW.md`)
| Layer | Key Components | Notes |
| --- | --- | --- |
| **Infrastructure** | Kubernetes, Docker, Kafka, CI/CD pipelines | Provides runtime, streaming backbone, automated delivery.
| **Data Stores** | PostgreSQL/PostGIS, TimescaleDB, MongoDB, Redis, InfluxDB, MSSQL (SCADA) | Spatial, time-series, document, cache/session, metrics, industrial data.
| **Gateway & Security** | Kong API Gateway, Auth service, User management, Audit service | Central routing, OAuth/JWT/Thai ID auth, RBAC, compliance logging.
| **Core Domain Services** | GIS, Sensor Data, SCADA integration, AI Model serving, Water Control | GIS PostGIS ops, ingest IoT/SCADA, ML inference, valve optimization.
| **Domain Extensions** | Crop management, Scheduling, Moisture, Water Level, Flow Monitoring, Weather monitoring | Sector-specific analytics feeding core control.
| **Integration Layer** | Weather/AOS connectors, ROS, RID services, Data Integration pipelines, IoT gateway | External data acquisition, ingestion, event stream processing.
| **Support Services** | Notification, Alerting, Configuration, Analytics, Maintenance, Reporting, Monitoring | Operational tooling and observability.
| **Optimization Services** | Optimization engine, Model Predictive Control | Advanced water allocation strategies.
| **Real-time APIs** | WebSocket service, GraphQL API | Live dashboards, bidirectional control.

## 3. Repository Layout (`README.md`, `docs/CODEBASE_STRUCTURE.md`)
```
/munbon2-backend
├── services/              # microservices (TypeScript, Go, Python, Java)
├── shared/                # shared TS libraries, proto definitions, DB schemas
├── infrastructure/        # k8s manifests, terraform, helm charts
├── scripts/               # deployment & utility automation
├── docs/                  # architecture, deployment, service guides
├── tests/                 # cross-service integration suites
├── docker-compose*.yml    # local & prod-like orchestration
└── package.json, Makefile # root tooling
```

Notable service directories (partial list):
- `api-gateway/`, `auth/`, `gis/`, `sensor-data/`, `scada/`, `ros/`, `water-control/`, `moisture-monitoring/`, `water-level-monitoring/`, `flow-monitoring/`, `smartfarm-water-control/`, `bff*` (frontends), `notification/`, `analytics/`, `scheduler/`, `user-management/`, `ai-model/`.

Shared assets:
- `shared/typescript-common/` – common TS middleware, utils, interfaces, constants.
- `shared/proto/` – gRPC/Protobuf contracts.
- `shared/database-schemas/` – canonical SQL definitions for PostgreSQL/timescale/mongo.

## 4. Data Flow – End-to-End Highlights
1. **Sensor Ingestion**: Field devices → IoT Gateway (Task 41) → Sensor Data Service (Go) via MQTT/HTTP → TimescaleDB hypertables.
2. **External Data**: Weather (TMD/AOS) & ROS runoff data ingested by integration services into weather monitoring & ROS services.
3. **Spatial Context**: GIS service uses PostGIS to manage canals, plots, infrastructure; shapefiles converted to GeoJSON for services like smart-farm water control.
4. **Optimization Loop**: Sensor + weather + ROS inputs → AI Model Service & Water Control Service → compute valve commands (AWD/moisture logic, OR-Tools, MPC) → SCADA integration writes to MSSQL `tb_valve_command_v2` to actuate solenoids.
5. **BFF/API Exposure**: Kong gateway routes to BFF services (web/mobile/water planning). BFFs aggregate data from core services for dashboards and manual overrides.
6. **Monitoring & Alerts**: Flow/level/moisture services publish metrics to monitoring stack (Prometheus/Grafana, InfluxDB), trigger alerts/notifications.

## 5. Databases & Schemas (key tables)
- **TimescaleDB (`sensor_data` cluster)**
  - `ros_gis_smartfarm.daily_water_demands`, `daily_progress`
  - `water_control_smartfarm.valve_status`, `irrigation_cycles`, `water_balance`
  - `moisture_readings`, `water_level_readings`
- **PostgreSQL/PostGIS**: GIS layers (plots, canals, basins).
- **MSSQL (`db_scada`)**: `tb_valve_command_v2` for valve actuation (fields: `valve_name`, `valve_level`, `startdatetime`).
- **MongoDB**: configuration documents, user preferences.
- **Redis**: session cache, rate limiting tokens.
- **InfluxDB**: operations telemetry.

## 6. Service Ports (`docs/PORT_ASSIGNMENTS.md`)
| Service | Port | Notes |
| --- | --- | --- |
| Unified API | 3000 | read-only aggregator |
| Auth | 3001 |
| Sensor Data API | 3003 |
| Sensor Consumer dashboard | 3004 |
| Moisture Monitoring | 3005 |
| Weather Monitoring | 3006 |
| GIS | 3007 |
| Water Level Monitoring | 3008 |
| AWD Control | 3010 |
| Flow Monitoring | 3011 |
| ROS | 3047 |
(*All ports overridable via env; no conflicts after reassignment.)

## 7. Smart Farm Water Control Snapshot (`services/smartfarm-water-control/`)
- GeoJSON-driven plot configuration (`data/smartfarm-plots.geojson`) producing precise UUID-based plot IDs and `area_rai` metadata.
- Environment variable `PLOT_CONFIGS` maps `plotId:sensorId:valveName:controlMode`.
- Services: moisture & AWD control logic, sensor data service (Timescale repository), valve command writer (MSSQL + Timescale logging), water planning (ROS integration), water balance analytics, Express API with cron-based planning/control loops.
- Tests: unit (service logic, config loader) + integration (control loop).

## 8. Deployment & Operations
- **Containerization**: Standard base images (Node 20-alpine, Python 3.11-slim, Go 1.21, Temurin JRE 17). Resource limits defined for k8s.
- **Kubernetes**: manifests under `infrastructure/kubernetes/` (namespace, ConfigMaps, secrets, service Deployments, StatefulSets for DBs, monitoring stack).
- **Terraform/Helm**: Infrastructure provisioning & packaging.
- **Scripts**: `scripts/deploy-*.sh`, `setup-all-services.sh`, `start-all-services.sh`, `pm2-*.config.js`, `deploy_*` for EC2.
- **Observability**: OpenTelemetry tracing, Prometheus metrics, Grafana dashboards, ELK logging (as per `docs/TECHNICAL_STACK.md`).
- **Operations Guides**: `docs/DEPLOYMENT_*`, `START_MICROSERVICES.md`, `TESTING_MICROSERVICES.md`, `TROUBLESHOOTING.md`.

## 9. Development Standards
- Node.js services: TypeScript 5, ESLint/Prettier, Jest, npm.
- Python services: Python 3.11, Black/Flake8/mypy, pytest, Poetry.
- Go services: Go 1.21, golangci-lint, testify.
- Java services: Java 17, Gradle, JUnit 5/Mockito.
- Shared code: TypeScript interfaces/middleware, proto contracts.
- Guidelines: `AGENTS.md`, `CLAUDE.md`, `PROGRAMMING_PRINCIPLES`, service-specific docs.

## 10. Key Documentation for Deeper Work
- Architecture & workflows: `docs/SYSTEM_E2E_FLOW.md`, `docs/architecture/…`
- Technical decisions: `docs/TECHNICAL_STACK.md`, `docs/PROJECT_STRUCTURE.md`, `docs/REALISTIC_SERVICE_ALLOCATION.md`.
- Ports & envs: `docs/PORT_ASSIGNMENTS.md`, `docs/SERVICE_ENV_GUIDE.md`.
- Deployment: `docs/DEPLOYMENT_*`, `docs/K3S_*`, `docs/DOCKER_*`, `docs/EC2_*`.
- Service blueprints: `docs/CLAUDE_INSTANCE_*` series for each domain service/BFF.

## 11. Critical Integration Points
- Sensor telemetry → Timescale + analytics services.
- ROS daily planning API → smart farm & water-control loops.
- SCADA MSSQL → valve command queue.
- Kafka event bus (data integration, analytics).
- API gateway ↔ BFFs ↔ frontends (web/mobile dashboards, control apps).

## 12. Usage Notes for Assistants
- Respect geojson/UUID workflow when modifying plot-based services.
- Schema updates must cover all Timescale tables referencing `plot_id`.
- Valve control path: service decision → MSSQL write → Timescale logging; ensure both sides stay in sync.
- When adding services, update port documents, k8s manifests, and shared config.
- Refer to `docs/CLAUDE_INSTANCES_MASTER.md` for task/service assignments before altering workflows.
- Always audit `.env` usage and confirm documentation updates alongside code changes.

