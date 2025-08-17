# ROS Service (Reservoir Operation System)

## Overview
The ROS Service handles water demand calculations and irrigation scheduling for the Munbon Irrigation Control System. It uses Excel-based ETo (evapotranspiration) and Kc (crop coefficient) data to calculate water requirements for different crops across various areas.

## Key Features
- Excel-based ETo and Kc data management
- Water demand calculation using FAO methodology
- Effective rainfall integration
- Water level monitoring
- Hierarchical area management (Project → Zone → Section)
- Crop calendar management
- Irrigation scheduling

## Technology Stack
- **Language**: TypeScript
- **Framework**: Express.js
- **Database**: PostgreSQL with PostGIS
- **Cache**: Redis
- **File Processing**: XLSX (for Excel imports)

## Setup Instructions

### Prerequisites
- Node.js 18+
- PostgreSQL 14+ with PostGIS extension
- Redis 6+

### Installation
```bash
# Navigate to service directory
cd services/ros

# Install dependencies
npm install

# Set up environment variables
cp .env.example .env
# Edit .env with your configuration

# Run database migrations
npm run db:migrate

# Seed initial data
npm run db:seed
```

### Environment Variables
```env
# Service Configuration
NODE_ENV=development
SERVICE_NAME=ros-service
SERVICE_PORT=3047

# Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5434
POSTGRES_USER=munbon_user
POSTGRES_PASSWORD=your_password
POSTGRES_DB=munbon_ros

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=

# JWT Configuration
JWT_SECRET=your_jwt_secret

# Weather API (optional)
WEATHER_API_KEY=your_api_key
```

## Water Demand Calculation

### Formula
```
Weekly Water Demand (mm) = (Weekly ETo × Kc) + Percolation
Water Demand (m³) = Water Demand (mm) × Area (rai) × 1.6
```

Where:
- **Weekly ETo**: Monthly ETo ÷ 4 (adjusted for month boundaries)
- **Kc**: Crop coefficient from Excel data
- **Percolation**: Fixed at 14 mm/week
- **1.6**: Conversion factor from mm×rai to m³

### Data Sources
1. **ETo Data**: Monthly values from Nakhon Ratchasima AOS station
2. **Kc Data**: Weekly values by crop type and growth stage
3. **Effective Rainfall**: From weather stations or manual entry
4. **Water Level**: From sensors or manual measurements

## API Endpoints

### Core Endpoints
- `POST /api/v1/ros/demand/calculate` - Calculate water demand
- `POST /api/v1/ros/eto/upload` - Upload ETo data from Excel
- `POST /api/v1/ros/kc/upload` - Upload Kc data from Excel
- `GET /api/v1/ros/areas/hierarchy/{projectId}` - Get area hierarchy

See [API_DOCUMENTATION.md](./API_DOCUMENTATION.md) for complete API reference.

## Development

### Running the Service
```bash
# Development mode
npm run dev

# Production mode
npm run build
npm start

# Run tests
npm test

# Lint code
npm run lint
```

### Project Structure
```
src/
├── config/          # Configuration files
├── controllers/     # Request handlers
├── services/        # Business logic
├── routes/          # API routes
├── middleware/      # Express middleware
├── utils/           # Utility functions
├── types/           # TypeScript types
└── index.ts         # Application entry point

scripts/
├── init-db.sql      # Database initialization
└── update-schema.sql # Schema updates
```

## Testing

### Unit Tests
```bash
npm run test:unit
```

### Integration Tests
```bash
npm run test:integration
```

### Test Coverage
```bash
npm run test:coverage
```

## Deployment

### Docker
```bash
docker build -t munbon/ros-service .
docker run -p 3047:3047 munbon/ros-service
```

### Kubernetes
```bash
kubectl apply -f k8s/ros-service.yaml
```

## Monitoring
- Health check: `GET /health`
- Metrics endpoint: `GET /metrics`
- Logs: Structured JSON logging to stdout

## Troubleshooting

### Common Issues

1. **Database Connection Failed**
   - Check PostgreSQL is running on port 5434
   - Verify database credentials
   - Ensure PostGIS extension is installed

2. **Excel Import Fails**
   - Download and use the provided templates
   - Check column headers match expected format
   - Verify data types (numbers, dates)

3. **Water Demand Calculation Error**
   - Ensure ETo data exists for the requested month
   - Verify Kc data exists for crop type and week
   - Check area information is properly configured

## Contributing
1. Create a feature branch
2. Make changes with tests
3. Run linter and tests
4. Submit pull request

## License
Proprietary - Munbon Irrigation Project