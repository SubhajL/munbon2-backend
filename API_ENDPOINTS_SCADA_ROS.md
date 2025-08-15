# 🚀 API Endpoints for SCADA & Water Management

## Base URLs
- **API Gateway**: `http://localhost:3000`
- **ROS Service**: `http://localhost:3047`
- **AWD Control**: `http://localhost:3010`
- **Flow Monitoring**: `http://localhost:3011`

---

## 1. 🔧 SCADA Health Check Endpoints

### Check SCADA Connection Status
```javascript
GET /api/scada/health
```

**Response:**
```json
{
  "status": "connected",
  "connectionType": "OPC_UA",
  "serverUrl": "opc.tcp://scada.munbon.local:4840",
  "lastHeartbeat": "2025-01-15T10:30:00Z",
  "latency": 45,
  "gates": {
    "total": 24,
    "online": 22,
    "offline": 2,
    "error": 0
  },
  "sensors": {
    "waterLevel": 15,
    "flow": 8,
    "pressure": 12
  }
}
```

### Check Individual Gate Status
```javascript
GET /api/scada/gates/:gateId/status
```

**Example:**
```javascript
// Check gate MG-01 status
fetch('http://localhost:3010/api/scada/gates/MG-01/status')
  .then(res => res.json())
  .then(data => console.log(data));
```

**Response:**
```json
{
  "gateId": "MG-01",
  "name": "Main Gate 01",
  "status": "online",
  "position": 65,  // 0-100% open
  "mode": "auto",  // auto/manual/maintenance
  "lastUpdate": "2025-01-15T10:29:45Z",
  "telemetry": {
    "upstream_level": 4.2,
    "downstream_level": 3.8,
    "flow_rate": 125.5,
    "power_status": "normal"
  }
}
```

### Get All Gates Status
```javascript
GET /api/scada/gates/status
```

**Response:**
```json
{
  "gates": [
    {
      "gateId": "MG-01",
      "name": "Main Gate 01",
      "zone": "zone-1",
      "section": "section-1A",
      "status": "online",
      "position": 65,
      "mode": "auto"
    },
    // ... more gates
  ],
  "summary": {
    "total": 24,
    "online": 22,
    "offline": 2,
    "open": 15,
    "closed": 7,
    "partial": 2
  }
}
```

---

## 2. 💧 Water Demand Calculation Endpoints (ROS)

### Calculate Weekly Water Demand by Section
```javascript
POST /api/water-demand/section/weekly
```

**Request Body:**
```json
{
  "sectionId": "section-1A",
  "week": 36,  // Week number (1-52)
  "year": 2025,
  "cropStage": "vegetative"  // optional, auto-detected if not provided
}
```

**Response:**
```json
{
  "sectionId": "section-1A",
  "week": 36,
  "year": 2025,
  "waterDemand": {
    "value": 12500,
    "unit": "m³",
    "dailyAverage": 1785.7,
    "peakDay": {
      "date": "2025-09-03",
      "demand": 2100
    }
  },
  "crops": [
    {
      "cropType": "rice",
      "area": 150,
      "plantingDate": "2025-06-15",
      "currentStage": "vegetative",
      "kc": 1.05,
      "waterRequirement": 8500
    },
    {
      "cropType": "sugarcane",
      "area": 75,
      "plantingDate": "2025-05-01",
      "currentStage": "grand_growth",
      "kc": 1.25,
      "waterRequirement": 4000
    }
  ],
  "weather": {
    "eto": 4.5,
    "rainfall": 12,
    "effectiveRainfall": 8.4
  }
}
```

### Calculate Weekly Water Demand by Zone
```javascript
POST /api/water-demand/zone/weekly
```

**Request Body:**
```json
{
  "zoneId": "zone-1",
  "week": 36,
  "year": 2025
}
```

**Response:**
```json
{
  "zoneId": "zone-1",
  "week": 36,
  "year": 2025,
  "waterDemand": {
    "total": 85000,
    "unit": "m³",
    "dailyAverage": 12142.9
  },
  "sections": [
    {
      "sectionId": "section-1A",
      "demand": 12500,
      "percentage": 14.7
    },
    {
      "sectionId": "section-1B",
      "demand": 15000,
      "percentage": 17.6
    },
    // ... more sections
  ],
  "distribution": {
    "monday": 11500,
    "tuesday": 12000,
    "wednesday": 12500,
    "thursday": 13000,
    "friday": 12000,
    "saturday": 11500,
    "sunday": 12500
  }
}
```

### Calculate Seasonal Water Demand (Whole Crop Cycle)
```javascript
POST /api/water-demand/seasonal
```

**Request Body:**
```json
{
  "zoneId": "zone-1",  // or sectionId for section-level
  "cropType": "rice",
  "plantingDate": "2025-06-15",
  "harvestDate": "2025-10-15"  // optional, calculated if not provided
}
```

**Response:**
```json
{
  "zoneId": "zone-1",
  "cropType": "rice",
  "season": {
    "plantingDate": "2025-06-15",
    "harvestDate": "2025-10-15",
    "duration": 122,
    "durationUnit": "days"
  },
  "waterDemand": {
    "total": 450000,
    "unit": "m³",
    "perRai": 562.5,
    "perHectare": 9000
  },
  "stages": [
    {
      "stage": "initial",
      "duration": 20,
      "demand": 45000,
      "percentage": 10
    },
    {
      "stage": "development",
      "duration": 30,
      "demand": 112500,
      "percentage": 25
    },
    {
      "stage": "mid_season",
      "duration": 60,
      "demand": 247500,
      "percentage": 55
    },
    {
      "stage": "late_season",
      "duration": 12,
      "demand": 45000,
      "percentage": 10
    }
  ],
  "weekly": [
    { "week": 25, "demand": 8500 },
    { "week": 26, "demand": 9200 },
    // ... all weeks
  ]
}
```

### Get Current Water Demand Summary
```javascript
GET /api/water-demand/current
```

**Query Parameters:**
- `level`: `zone` | `section` | `field` (default: zone)
- `id`: Zone/Section/Field ID (optional, returns all if not specified)

**Example:**
```javascript
// Get current demand for all zones
fetch('http://localhost:3047/api/water-demand/current?level=zone')

// Get current demand for specific section
fetch('http://localhost:3047/api/water-demand/current?level=section&id=section-1A')
```

---

## 3. 🚪 Gate Control Command Endpoints

### Open/Close Single Gate
```javascript
POST /api/scada/gates/:gateId/control
```

**Request Body:**
```json
{
  "command": "set_position",
  "position": 75,  // 0-100% (0=closed, 100=fully open)
  "mode": "manual",
  "reason": "Irrigation schedule",
  "duration": 3600  // optional, auto-close after seconds
}
```

**Example:**
```javascript
// Open gate MG-01 to 75%
fetch('http://localhost:3010/api/scada/gates/MG-01/control', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    command: 'set_position',
    position: 75,
    reason: 'Morning irrigation'
  })
})
```

**Response:**
```json
{
  "success": true,
  "gateId": "MG-01",
  "command": "set_position",
  "targetPosition": 75,
  "currentPosition": 65,
  "estimatedTime": 30,  // seconds to reach position
  "status": "moving",
  "timestamp": "2025-01-15T10:35:00Z"
}
```

### Batch Gate Control (Multiple Gates)
```javascript
POST /api/scada/gates/batch-control
```

**Request Body:**
```json
{
  "gates": [
    {
      "gateId": "MG-01",
      "position": 100,
      "priority": 1
    },
    {
      "gateId": "MG-02",
      "position": 75,
      "priority": 2
    },
    {
      "gateId": "SG-01",
      "position": 50,
      "priority": 3
    }
  ],
  "mode": "sequential",  // sequential | parallel
  "reason": "Zone 1 irrigation schedule"
}
```

**Response:**
```json
{
  "batchId": "batch-2025-01-15-001",
  "status": "executing",
  "gates": [
    {
      "gateId": "MG-01",
      "status": "completed",
      "position": 100
    },
    {
      "gateId": "MG-02",
      "status": "moving",
      "currentPosition": 45,
      "targetPosition": 75
    },
    {
      "gateId": "SG-01",
      "status": "queued",
      "targetPosition": 50
    }
  ],
  "estimatedCompletion": "2025-01-15T10:37:30Z"
}
```

### Execute Irrigation Schedule
```javascript
POST /api/irrigation/execute-schedule
```

**Request Body:**
```json
{
  "scheduleId": "daily-zone-1",
  "date": "2025-01-15",
  "waterDemand": 12500,  // m³
  "duration": 14400,  // seconds (4 hours)
  "sections": ["section-1A", "section-1B"],
  "autoAdjust": true  // Adjust based on current water levels
}
```

**Response:**
```json
{
  "executionId": "exec-2025-01-15-001",
  "status": "active",
  "schedule": {
    "start": "2025-01-15T06:00:00Z",
    "end": "2025-01-15T10:00:00Z",
    "waterTarget": 12500,
    "waterDelivered": 3125,  // real-time update
    "progress": 25
  },
  "gates": [
    {
      "gateId": "MG-01",
      "action": "opened",
      "position": 100,
      "flow": 125.5
    },
    {
      "gateId": "SG-01",
      "action": "opened",
      "position": 75,
      "flow": 85.2
    }
  ],
  "monitoring": {
    "upstream_level": 4.5,
    "downstream_level": 3.2,
    "total_flow": 210.7,
    "efficiency": 92.5
  }
}
```

### Emergency Stop All Gates
```javascript
POST /api/scada/gates/emergency-stop
```

**Request Body:**
```json
{
  "reason": "Flood warning",
  "zones": ["zone-1", "zone-2"],  // optional, all if not specified
  "notifyOperators": true
}
```

**Response:**
```json
{
  "success": true,
  "gatesClosed": 24,
  "timeToComplete": 45,  // seconds
  "status": "emergency_shutdown",
  "notifications": [
    {
      "operator": "John Doe",
      "method": "SMS",
      "status": "sent"
    }
  ]
}
```

---

## 📊 WebSocket Real-time Updates

### Subscribe to Gate Status Updates
```javascript
const ws = new WebSocket('ws://localhost:3010/ws/gates');

ws.onmessage = (event) => {
  const update = JSON.parse(event.data);
  console.log('Gate update:', update);
  // {
  //   "gateId": "MG-01",
  //   "position": 67,
  //   "status": "moving",
  //   "flow": 115.3
  // }
};
```

### Subscribe to Water Demand Updates
```javascript
const ws = new WebSocket('ws://localhost:3047/ws/demand');

ws.onmessage = (event) => {
  const update = JSON.parse(event.data);
  console.log('Demand update:', update);
  // {
  //   "zoneId": "zone-1",
  //   "currentDemand": 185.5,  // m³/hr
  //   "dailyProgress": 8500,    // m³ delivered today
  //   "efficiency": 94.2
  // }
};
```

---

## 🧪 Testing Endpoints

### Test with cURL

```bash
# 1. Check SCADA health
curl http://localhost:3010/api/scada/health

# 2. Calculate water demand for section
curl -X POST http://localhost:3047/api/water-demand/section/weekly \
  -H "Content-Type: application/json" \
  -d '{"sectionId":"section-1A","week":36,"year":2025}'

# 3. Open gate
curl -X POST http://localhost:3010/api/scada/gates/MG-01/control \
  -H "Content-Type: application/json" \
  -d '{"command":"set_position","position":75}'
```

### Test with JavaScript

```javascript
// Complete flow test
async function testIrrigationFlow() {
  // 1. Check SCADA health
  const health = await fetch('http://localhost:3010/api/scada/health')
    .then(res => res.json());
  console.log('SCADA Status:', health.status);
  
  // 2. Calculate water demand
  const demand = await fetch('http://localhost:3047/api/water-demand/zone/weekly', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      zoneId: 'zone-1',
      week: 36,
      year: 2025
    })
  }).then(res => res.json());
  console.log('Water Demand:', demand.waterDemand.total);
  
  // 3. Open gates based on demand
  const gateControl = await fetch('http://localhost:3010/api/scada/gates/batch-control', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      gates: [
        { gateId: 'MG-01', position: 100, priority: 1 },
        { gateId: 'MG-02', position: 75, priority: 2 }
      ],
      mode: 'sequential',
      reason: `Irrigation for ${demand.waterDemand.total}m³`
    })
  }).then(res => res.json());
  console.log('Gates Status:', gateControl.status);
  
  return { health, demand, gateControl };
}

// Run test
testIrrigationFlow().then(console.log);
```

---

## 🔐 Authentication Headers

For production, add authentication:

```javascript
const headers = {
  'Content-Type': 'application/json',
  'Authorization': 'Bearer YOUR_TOKEN_HERE',
  'X-API-Key': 'YOUR_API_KEY'  // For SCADA endpoints
};
```

For debug mode:
```javascript
const headers = {
  'Content-Type': 'application/json',
  'Authorization': 'Bearer debug-token'
};
```