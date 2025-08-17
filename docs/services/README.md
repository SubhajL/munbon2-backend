# Microservices

This directory contains all microservices for the Munbon Irrigation Control System.

## Services Overview

### Node.js/TypeScript Services
- **api-gateway** - API Gateway for routing and load balancing
- **auth** - Authentication and authorization service
- **gis** - GIS data and spatial operations service
- **user-management** - User profile and role management
- **weather** - Weather data integration service
- **notification** - Multi-channel notification service
- **alert-management** - Alert rules and management
- **configuration** - Centralized configuration service
- **bff** - Backend for Frontend service with GraphQL
- **websocket** - Real-time WebSocket service
- **reporting** - Report generation service
- **file-processing** - File upload and processing service
- **maintenance** - Equipment maintenance tracking

### Python Services
- **ai-model** - AI/ML model serving
- **analytics** - Data analytics service
- **data-integration** - ETL and data integration
- **crop-management** - Crop data and AquaCrop integration

### Go Services
- **sensor-data** - High-throughput sensor data ingestion
- **scada** - SCADA integration service
- **monitoring** - System monitoring service

### Java Services
- **water-control** - Water distribution control and optimization

## Development Guidelines

Each service should:
1. Have its own README with specific setup instructions
2. Include health check endpoints
3. Follow the project's coding standards
4. Have comprehensive test coverage
5. Include Docker configuration for containerization