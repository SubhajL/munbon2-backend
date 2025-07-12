# Claude Instance 7: Setup BFF Service

## Scope of Work
This instance handles the Backend-for-Frontend service dedicated to system setup, configuration, and onboarding workflows.

## Assigned Components

### 1. **Setup BFF Service** (Primary)
- **Path**: `/services/bff-setup`
- **Port**: 4001
- **Responsibilities**:
  - User onboarding and registration
  - Zone configuration and mapping
  - Sensor registration and configuration
  - Initial system setup workflows
  - Bulk import operations
  - Configuration wizards

### 2. **Integration with Core Services**
- **Auth Service**: User registration, role assignment
- **GIS Service**: SHAPE file processing, zone creation
- **Sensor Service**: Device registration, configuration
- **Config Service**: System parameters setup

## Environment Setup

```bash
# Setup BFF Service
cat > services/bff-setup/.env.local << EOF
SERVICE_NAME=bff-setup
PORT=4001
NODE_ENV=development

# GraphQL Configuration
GRAPHQL_PATH=/graphql
GRAPHQL_PLAYGROUND=true
GRAPHQL_INTROSPECTION=true

# Internal Services
AUTH_SERVICE_URL=http://localhost:3001
GIS_SERVICE_URL=http://localhost:3007
SENSOR_SERVICE_URL=http://localhost:3003
CONFIG_SERVICE_URL=http://localhost:3033
USER_SERVICE_URL=http://localhost:3002

# Database (for BFF-specific data)
DB_HOST=localhost
DB_PORT=5434
DB_NAME=munbon_bff
DB_USER=postgres
DB_PASSWORD=postgres123

# Redis Cache
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=9
CACHE_TTL_DEFAULT=300

# File Upload
MAX_FILE_SIZE=100MB
UPLOAD_DIR=/tmp/bff-setup-uploads
ALLOWED_FILE_TYPES=shp,zip,csv,xlsx

# Thai National ID Validation
THAI_ID_VALIDATION_URL=https://api.dopa.go.th/validate
THAI_ID_API_KEY=your-api-key

# Session Configuration
SESSION_SECRET=setup-bff-secret-key
SESSION_TIMEOUT=3600000  # 1 hour

# Rate Limiting
RATE_LIMIT_SETUP=10  # 10 requests per minute for setup operations
EOF
```

## GraphQL Schema

```graphql
type Mutation {
  # User Onboarding
  registerFarmer(input: FarmerRegistrationInput!): FarmerRegistrationResult!
  bulkImportFarmers(file: Upload!): BulkImportResult!
  
  # Zone Setup
  createZone(input: ZoneCreationInput!): Zone!
  uploadShapeFile(file: Upload!, zoneId: ID!): ShapeFileUploadResult!
  assignZoneManager(zoneId: ID!, userId: ID!): Zone!
  
  # Sensor Registration
  registerSensor(input: SensorRegistrationInput!): Sensor!
  configureSensorThresholds(sensorId: ID!, thresholds: ThresholdInput!): Sensor!
  mapSensorToLocation(sensorId: ID!, location: LocationInput!): Sensor!
  
  # System Configuration
  configureIrrigationDefaults(input: IrrigationDefaultsInput!): SystemConfig!
  setupCropCalendar(input: CropCalendarInput!): CropCalendar!
  configureNotificationPreferences(input: NotificationPrefsInput!): UserPreferences!
}

type Query {
  # Setup Progress
  getOnboardingProgress(userId: ID!): OnboardingProgress!
  getSystemSetupStatus: SystemSetupStatus!
  
  # Validation
  validateThaiNationalId(id: String!): ValidationResult!
  validateLandParcel(parcelId: String!): ParcelValidation!
  
  # Templates and Defaults
  getZoneTemplates: [ZoneTemplate!]!
  getSensorTypes: [SensorType!]!
  getCropTypes: [CropType!]!
  getDefaultThresholds(sensorType: String!): ThresholdDefaults!
}

type Subscription {
  onboardingProgress(userId: ID!): OnboardingProgress!
  setupTaskStatus(taskId: ID!): SetupTaskStatus!
}
```

## Setup Workflows

### 1. Farmer Registration Flow
```javascript
async function registerFarmer(input) {
  // Step 1: Validate Thai National ID
  const idValidation = await validateThaiId(input.nationalId);
  
  // Step 2: Create user in Auth Service
  const user = await authService.createUser({
    ...input,
    role: 'FARMER'
  });
  
  // Step 3: Register land parcels in GIS
  const parcels = await gisService.registerParcels(
    input.landParcels,
    user.id
  );
  
  // Step 4: Set up initial preferences
  await configService.setUserPreferences(user.id, {
    language: input.language || 'th',
    notifications: input.notificationPrefs
  });
  
  // Step 5: Create onboarding checklist
  const checklist = await createOnboardingChecklist(user.id);
  
  return {
    user,
    parcels,
    checklist
  };
}
```

### 2. Zone Configuration Flow
```javascript
async function configureZone(shapeFile, zoneConfig) {
  // Step 1: Process SHAPE file
  const gisData = await gisService.processShapeFile(shapeFile);
  
  // Step 2: Validate zone boundaries
  const validation = await validateZoneBoundaries(gisData);
  
  // Step 3: Create zone with configuration
  const zone = await gisService.createZone({
    geometry: gisData.geometry,
    ...zoneConfig
  });
  
  // Step 4: Auto-detect sensors in zone
  const sensors = await sensorService.findSensorsInBounds(
    zone.boundaries
  );
  
  // Step 5: Set up default schedules
  const schedules = await createDefaultSchedules(zone);
  
  return {
    zone,
    sensors,
    schedules
  };
}
```

## API Endpoints

### REST Endpoints (for file uploads)
```
POST /api/v1/setup/upload/farmers-csv
POST /api/v1/setup/upload/shapefile
POST /api/v1/setup/upload/sensor-config
GET /api/v1/setup/templates/{type}
GET /api/v1/setup/progress/{userId}
```

### GraphQL Endpoint
```
POST /graphql
GET /graphql (playground in dev)
WS /graphql (subscriptions)
```

## Current Status
- ❌ Service structure: Not created
- ❌ GraphQL schema: Not implemented
- ❌ File upload handling: Not implemented
- ❌ Thai ID validation: Not integrated
- ❌ Onboarding workflows: Not built

## Priority Tasks
1. Create service boilerplate with TypeScript
2. Implement GraphQL schema with Apollo Server
3. Build file upload handlers for SHAPE/CSV
4. Integrate Thai National ID validation
5. Create onboarding workflow engine
6. Build zone configuration wizard
7. Implement sensor registration flow
8. Create progress tracking system

## Testing Commands

```bash
# Test farmer registration
curl -X POST http://localhost:4001/graphql \
  -H "Content-Type: application/json" \
  -d '{
    "query": "mutation { registerFarmer(input: { nationalId: \"1234567890123\", name: \"สมชาย ชาวนา\", phone: \"0812345678\" }) { user { id name } } }"
  }'

# Upload SHAPE file
curl -X POST http://localhost:4001/api/v1/setup/upload/shapefile \
  -F "file=@zone1.zip" \
  -F "zoneConfig={\"name\":\"Zone 1\",\"type\":\"irrigation\"}"

# Check setup progress
curl http://localhost:4001/api/v1/setup/progress/USER123
```

## Integration Points

### With Auth Service
```javascript
// Create user with farmer role
const user = await authService.createUser({
  email,
  password,
  role: 'FARMER',
  metadata: { nationalId, landParcels }
});
```

### With GIS Service
```javascript
// Process uploaded SHAPE file
const processedData = await gisService.processShapeFile(fileBuffer);
const zone = await gisService.createZone(processedData);
```

### With Config Service
```javascript
// Store system-wide defaults
await configService.setSystemDefaults({
  irrigationEfficiency: 0.85,
  defaultCropType: 'RICE',
  seasonalCalendar: {...}
});
```

## Notes for Development
- Use GraphQL for complex workflows
- Implement file upload progress tracking
- Add validation at each step
- Create reusable setup templates
- Support bulk operations
- Implement undo/rollback for setup steps
- Add comprehensive audit logging
- Support multiple languages (Thai/English)