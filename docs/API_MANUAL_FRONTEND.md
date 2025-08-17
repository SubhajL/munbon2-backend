# API Manual for Frontend Team
## Munbon Irrigation Control System

**Version**: 1.0.0  
**Date**: January 15, 2025  
**Backend Team Contact**: backend-team@munbon.th

---

## Table of Contents
1. [Getting Started](#getting-started)
2. [Authentication](#authentication)
3. [Base URLs](#base-urls)
4. [SCADA System APIs](#scada-system-apis)
5. [Water Demand APIs](#water-demand-apis)
6. [Gate Control APIs](#gate-control-apis)
7. [Irrigation Scheduling APIs](#irrigation-scheduling-apis)
8. [WebSocket Real-time Updates](#websocket-real-time-updates)
9. [Error Handling](#error-handling)
10. [Rate Limiting](#rate-limiting)
11. [Testing](#testing)
12. [FAQ](#faq)

---

## Getting Started

### Prerequisites
- Node.js 16+ (for JavaScript/TypeScript examples)
- Modern browser with fetch API support
- WebSocket support for real-time updates

### Quick Start
```javascript
// Import this configuration in your app
const API_CONFIG = {
  AWD_SERVICE: 'http://localhost:3010',
  ROS_SERVICE: 'http://localhost:3047',
  AUTH_TOKEN: 'Bearer debug-token', // For development
  TIMEOUT: 30000 // 30 seconds
};

// Basic API call helper
async function apiCall(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'Authorization': API_CONFIG.AUTH_TOKEN,
      ...options.headers
    }
  });
  
  if (!response.ok) {
    throw new Error(`API Error: ${response.status} ${response.statusText}`);
  }
  
  return response.json();
}
```

---

## Authentication

### Development Environment
```javascript
// No authentication required - use debug token
headers: {
  'Authorization': 'Bearer debug-token'
}
```

### Production Environment
```javascript
// Login to get JWT token
const loginResponse = await fetch('/api/auth/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    username: 'user@example.com',
    password: 'password'
  })
});

const { token } = await loginResponse.json();

// Use token in subsequent requests
headers: {
  'Authorization': `Bearer ${token}`
}
```

---

## Base URLs

| Service | Development | Production | Description |
|---------|------------|------------|-------------|
| AWD Control | `http://localhost:3010` | `https://api.munbon.th/awd` | Gate control & SCADA |
| ROS Service | `http://localhost:3047` | `https://api.munbon.th/ros` | Water demand calculations |
| Auth Service | `http://localhost:3001` | `https://api.munbon.th/auth` | Authentication |

---

## SCADA System APIs

### 1. Check SCADA Health Status

**Purpose**: Verify SCADA system connectivity and get overview of gates and sensors.

**Endpoint**: `GET /api/scada/health`

**Request Example**:
```javascript
const checkScadaHealth = async () => {
  const response = await fetch('http://localhost:3010/api/scada/health');
  return response.json();
};
```

**Response**:
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

**Frontend Usage**:
```javascript
// Component: ScadaHealthIndicator.jsx
const ScadaHealthIndicator = () => {
  const [health, setHealth] = useState(null);
  
  useEffect(() => {
    const checkHealth = async () => {
      try {
        const data = await checkScadaHealth();
        setHealth(data);
      } catch (error) {
        console.error('SCADA health check failed:', error);
      }
    };
    
    checkHealth();
    const interval = setInterval(checkHealth, 30000); // Check every 30s
    return () => clearInterval(interval);
  }, []);
  
  return (
    <div className="scada-health">
      <StatusIndicator status={health?.status} />
      <span>Gates: {health?.gates.online}/{health?.gates.total}</span>
      <span>Latency: {health?.latency}ms</span>
    </div>
  );
};
```

### 2. Get Individual Gate Status

**Purpose**: Get detailed information about a specific gate.

**Endpoint**: `GET /api/scada/gates/:gateId/status`

**Parameters**:
- `gateId` (path): Gate identifier (e.g., "MG-01", "SG-02")

**Request Example**:
```javascript
const getGateStatus = async (gateId) => {
  const response = await fetch(`http://localhost:3010/api/scada/gates/${gateId}/status`);
  return response.json();
};
```

**Response**:
```json
{
  "gateId": "MG-01",
  "name": "Main Gate 01",
  "status": "online",
  "position": 65,
  "mode": "auto",
  "lastUpdate": "2025-01-15T10:29:45Z",
  "telemetry": {
    "upstream_level": 4.2,
    "downstream_level": 3.8,
    "flow_rate": 125.5,
    "power_status": "normal"
  }
}
```

### 3. Get All Gates Status

**Purpose**: Get status overview of all gates in the system.

**Endpoint**: `GET /api/scada/gates/status`

**Request Example**:
```javascript
const getAllGatesStatus = async () => {
  const response = await fetch('http://localhost:3010/api/scada/gates/status');
  return response.json();
};
```

**Response**:
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
    }
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

**Frontend Component Example**:
```javascript
// GatesDashboard.jsx
const GatesDashboard = () => {
  const [gates, setGates] = useState([]);
  const [summary, setSummary] = useState({});
  
  useEffect(() => {
    getAllGatesStatus().then(data => {
      setGates(data.gates);
      setSummary(data.summary);
    });
  }, []);
  
  return (
    <div className="gates-dashboard">
      <div className="summary">
        <Card title="Total Gates" value={summary.total} />
        <Card title="Online" value={summary.online} color="green" />
        <Card title="Offline" value={summary.offline} color="red" />
      </div>
      <GatesList gates={gates} />
    </div>
  );
};
```

---

## Water Demand APIs

### 1. Calculate Weekly Water Demand by Section

**Purpose**: Calculate water requirements for a specific section for a given week.

**Endpoint**: `POST /api/water-demand/section/weekly`

**Request Body**:
```json
{
  "sectionId": "section-1A",
  "week": 36,
  "year": 2025,
  "cropStage": "vegetative"
}
```

**Parameters**:
- `sectionId` (required): Section identifier
- `week` (required): Week number (1-52)
- `year` (required): Year
- `cropStage` (optional): Current crop stage

**Request Example**:
```javascript
const calculateSectionDemand = async (sectionId, week, year) => {
  const response = await fetch('http://localhost:3047/api/water-demand/section/weekly', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sectionId, week, year })
  });
  return response.json();
};
```

**Response**:
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
    }
  ],
  "weather": {
    "eto": 4.5,
    "rainfall": 12,
    "effectiveRainfall": 8.4
  }
}
```

### 2. Calculate Weekly Water Demand by Zone

**Purpose**: Calculate aggregated water requirements for an entire zone.

**Endpoint**: `POST /api/water-demand/zone/weekly`

**Request Body**:
```json
{
  "zoneId": "zone-1",
  "week": 36,
  "year": 2025
}
```

**Response**:
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
    }
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

### 3. Calculate Seasonal Water Demand

**Purpose**: Calculate total water requirements for an entire crop season.

**Endpoint**: `POST /api/water-demand/seasonal`

**Request Body**:
```json
{
  "zoneId": "zone-1",
  "cropType": "rice",
  "plantingDate": "2025-06-15",
  "harvestDate": "2025-10-15"
}
```

**Response**:
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
    }
  ],
  "weekly": [
    { "week": 25, "demand": 8500 }
  ]
}
```

### 4. Get Current Water Demand

**Purpose**: Get real-time water demand at various levels.

**Endpoint**: `GET /api/water-demand/current`

**Query Parameters**:
- `level`: "zone" | "section" | "field"
- `id`: Specific zone/section/field ID (optional)

**Request Example**:
```javascript
// Get all zones
const getCurrentDemand = async () => {
  const response = await fetch('http://localhost:3047/api/water-demand/current?level=zone');
  return response.json();
};

// Get specific section
const getSectionDemand = async (sectionId) => {
  const response = await fetch(
    `http://localhost:3047/api/water-demand/current?level=section&id=${sectionId}`
  );
  return response.json();
};
```

---

## Gate Control APIs

### 1. Control Single Gate

**Purpose**: Open, close, or adjust a single gate position.

**Endpoint**: `POST /api/scada/gates/:gateId/control`

**Request Body**:
```json
{
  "command": "set_position",
  "position": 75,
  "mode": "manual",
  "reason": "Irrigation schedule",
  "duration": 3600
}
```

**Parameters**:
- `command`: "set_position" | "open" | "close"
- `position`: 0-100 (percentage open)
- `mode`: "manual" | "auto" | "maintenance"
- `reason`: Description of why gate is being controlled
- `duration` (optional): Auto-close after seconds

**Request Example**:
```javascript
const controlGate = async (gateId, position, reason) => {
  const response = await fetch(`http://localhost:3010/api/scada/gates/${gateId}/control`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      command: 'set_position',
      position,
      mode: 'manual',
      reason
    })
  });
  return response.json();
};
```

**Response**:
```json
{
  "success": true,
  "gateId": "MG-01",
  "command": "set_position",
  "targetPosition": 75,
  "currentPosition": 65,
  "estimatedTime": 30,
  "status": "moving",
  "timestamp": "2025-01-15T10:35:00Z"
}
```

### 2. Batch Gate Control

**Purpose**: Control multiple gates simultaneously or sequentially.

**Endpoint**: `POST /api/scada/gates/batch-control`

**Request Body**:
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
    }
  ],
  "mode": "sequential",
  "reason": "Zone 1 irrigation schedule"
}
```

**Parameters**:
- `gates`: Array of gate control objects
- `mode`: "sequential" | "parallel"
- `reason`: Description of batch operation

**Frontend Example**:
```javascript
// GateControlPanel.jsx
const GateControlPanel = ({ zone }) => {
  const [executing, setExecuting] = useState(false);
  
  const openZoneGates = async () => {
    setExecuting(true);
    try {
      const gates = zone.gates.map((gate, index) => ({
        gateId: gate.id,
        position: gate.recommendedPosition,
        priority: index + 1
      }));
      
      const result = await fetch('http://localhost:3010/api/scada/gates/batch-control', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          gates,
          mode: 'sequential',
          reason: `Irrigation for ${zone.name}`
        })
      }).then(res => res.json());
      
      console.log('Batch execution started:', result.batchId);
    } finally {
      setExecuting(false);
    }
  };
  
  return (
    <button onClick={openZoneGates} disabled={executing}>
      {executing ? 'Opening Gates...' : 'Open Zone Gates'}
    </button>
  );
};
```

### 3. Emergency Stop

**Purpose**: Immediately close all gates in case of emergency.

**Endpoint**: `POST /api/scada/gates/emergency-stop`

**Request Body**:
```json
{
  "reason": "Flood warning",
  "zones": ["zone-1", "zone-2"],
  "notifyOperators": true
}
```

**Response**:
```json
{
  "success": true,
  "gatesClosed": 24,
  "timeToComplete": 45,
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

## Irrigation Scheduling APIs

### Execute Irrigation Schedule

**Purpose**: Execute a complete irrigation schedule with automatic gate control.

**Endpoint**: `POST /api/irrigation/execute-schedule`

**Request Body**:
```json
{
  "scheduleId": "daily-zone-1",
  "date": "2025-01-15",
  "waterDemand": 12500,
  "duration": 14400,
  "sections": ["section-1A", "section-1B"],
  "autoAdjust": true
}
```

**Parameters**:
- `scheduleId`: Unique schedule identifier
- `date`: Execution date
- `waterDemand`: Target water volume (m³)
- `duration`: Duration in seconds
- `sections`: Array of section IDs
- `autoAdjust`: Auto-adjust gates based on water levels

**Response**:
```json
{
  "executionId": "exec-2025-01-15-001",
  "status": "active",
  "schedule": {
    "start": "2025-01-15T06:00:00Z",
    "end": "2025-01-15T10:00:00Z",
    "waterTarget": 12500,
    "waterDelivered": 3125,
    "progress": 25
  },
  "gates": [
    {
      "gateId": "MG-01",
      "action": "opened",
      "position": 100,
      "flow": 125.5
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

**Complete Flow Example**:
```javascript
// IrrigationScheduler.jsx
const IrrigationScheduler = () => {
  const [executing, setExecuting] = useState(false);
  const [execution, setExecution] = useState(null);
  
  const executeIrrigation = async () => {
    setExecuting(true);
    
    try {
      // Step 1: Calculate water demand
      const demandResponse = await fetch('http://localhost:3047/api/water-demand/zone/weekly', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          zoneId: 'zone-1',
          week: getCurrentWeek(),
          year: new Date().getFullYear()
        })
      });
      const demand = await demandResponse.json();
      
      // Step 2: Execute schedule
      const execResponse = await fetch('http://localhost:3010/api/irrigation/execute-schedule', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          scheduleId: `schedule-${Date.now()}`,
          date: new Date().toISOString().split('T')[0],
          waterDemand: demand.waterDemand.total,
          duration: 14400, // 4 hours
          sections: ['section-1A', 'section-1B'],
          autoAdjust: true
        })
      });
      const execution = await execResponse.json();
      
      setExecution(execution);
      
      // Step 3: Monitor progress
      const interval = setInterval(async () => {
        const statusResponse = await fetch(
          `http://localhost:3010/api/irrigation/status/${execution.executionId}`
        );
        const status = await statusResponse.json();
        
        setExecution(status);
        
        if (status.schedule.progress >= 100) {
          clearInterval(interval);
          setExecuting(false);
        }
      }, 5000); // Check every 5 seconds
      
    } catch (error) {
      console.error('Irrigation execution failed:', error);
      setExecuting(false);
    }
  };
  
  return (
    <div className="irrigation-scheduler">
      <button onClick={executeIrrigation} disabled={executing}>
        Start Irrigation
      </button>
      
      {execution && (
        <div className="execution-status">
          <ProgressBar value={execution.schedule.progress} />
          <p>Water Delivered: {execution.schedule.waterDelivered}m³</p>
          <p>Efficiency: {execution.monitoring.efficiency}%</p>
        </div>
      )}
    </div>
  );
};
```

---

## WebSocket Real-time Updates

### Gate Status Updates

**Connection**:
```javascript
const gateWs = new WebSocket('ws://localhost:3010/ws/gates');

gateWs.onopen = () => {
  console.log('Connected to gate status updates');
};

gateWs.onmessage = (event) => {
  const update = JSON.parse(event.data);
  // update = { gateId: "MG-01", position: 75, status: "moving", flow: 125.5 }
  updateGateStatus(update);
};

gateWs.onerror = (error) => {
  console.error('WebSocket error:', error);
};

gateWs.onclose = () => {
  console.log('Disconnected from gate updates');
  // Implement reconnection logic
};
```

### Water Demand Updates

**Connection**:
```javascript
const demandWs = new WebSocket('ws://localhost:3047/ws/demand');

demandWs.onmessage = (event) => {
  const update = JSON.parse(event.data);
  // update = { zoneId: "zone-1", currentDemand: 185.5, dailyProgress: 8500, efficiency: 94.2 }
  updateDemandDisplay(update);
};
```

### React Hook for WebSocket

```javascript
// useWebSocket.js
import { useEffect, useRef, useState } from 'react';

export const useWebSocket = (url) => {
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState(null);
  const ws = useRef(null);
  
  useEffect(() => {
    ws.current = new WebSocket(url);
    
    ws.current.onopen = () => setIsConnected(true);
    ws.current.onclose = () => setIsConnected(false);
    ws.current.onmessage = (event) => {
      setLastMessage(JSON.parse(event.data));
    };
    
    return () => {
      ws.current?.close();
    };
  }, [url]);
  
  const sendMessage = (message) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(message));
    }
  };
  
  return { isConnected, lastMessage, sendMessage };
};

// Usage in component
const GateMonitor = () => {
  const { isConnected, lastMessage } = useWebSocket('ws://localhost:3010/ws/gates');
  
  useEffect(() => {
    if (lastMessage) {
      console.log('Gate update:', lastMessage);
    }
  }, [lastMessage]);
  
  return (
    <div>
      Status: {isConnected ? 'Connected' : 'Disconnected'}
    </div>
  );
};
```

---

## Error Handling

### Standard Error Response Format

```json
{
  "error": "Error type",
  "message": "Human-readable error message",
  "details": {
    "field": "Additional error details"
  },
  "timestamp": "2025-01-15T10:00:00Z"
}
```

### HTTP Status Codes

| Code | Meaning | Action |
|------|---------|--------|
| 200 | Success | Process response |
| 201 | Created | Resource created successfully |
| 400 | Bad Request | Check request parameters |
| 401 | Unauthorized | Refresh authentication token |
| 403 | Forbidden | Check user permissions |
| 404 | Not Found | Resource doesn't exist |
| 429 | Too Many Requests | Implement backoff strategy |
| 500 | Server Error | Retry with exponential backoff |
| 503 | Service Unavailable | Service temporarily down |

### Error Handling Example

```javascript
class ApiClient {
  async request(url, options = {}) {
    try {
      const response = await fetch(url, {
        ...options,
        headers: {
          'Content-Type': 'application/json',
          'Authorization': this.token,
          ...options.headers
        }
      });
      
      if (!response.ok) {
        const error = await response.json();
        throw new ApiError(response.status, error.message, error.details);
      }
      
      return response.json();
    } catch (error) {
      if (error instanceof ApiError) {
        throw error;
      }
      
      // Network error
      throw new NetworkError('Network request failed', error);
    }
  }
  
  async retryWithBackoff(fn, maxRetries = 3) {
    let lastError;
    
    for (let i = 0; i < maxRetries; i++) {
      try {
        return await fn();
      } catch (error) {
        lastError = error;
        
        if (error.status === 429 || error.status >= 500) {
          // Exponential backoff: 1s, 2s, 4s
          await new Promise(resolve => setTimeout(resolve, Math.pow(2, i) * 1000));
          continue;
        }
        
        throw error;
      }
    }
    
    throw lastError;
  }
}
```

---

## Rate Limiting

### Limits

| Endpoint Type | Limit | Window |
|--------------|-------|--------|
| Read operations | 100 requests | 1 minute |
| Write operations | 30 requests | 1 minute |
| Batch operations | 10 requests | 1 minute |
| WebSocket connections | 5 per client | - |

### Rate Limit Headers

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1673884800
```

### Handling Rate Limits

```javascript
const handleRateLimit = async (response) => {
  if (response.status === 429) {
    const resetTime = response.headers.get('X-RateLimit-Reset');
    const waitTime = resetTime ? (resetTime * 1000 - Date.now()) : 60000;
    
    console.log(`Rate limited. Waiting ${waitTime}ms`);
    await new Promise(resolve => setTimeout(resolve, waitTime));
    
    // Retry the request
    return true;
  }
  return false;
};
```

---

## Testing

### Development Testing

```bash
# 1. Start backend services
docker-compose -f docker-compose.debug.yml up -d

# 2. Run API tests
./test-scada-ros-endpoints.sh

# 3. Check service health
curl http://localhost:3010/health
curl http://localhost:3047/health
```

### Frontend Integration Testing

```javascript
// test-api.js
import { describe, it, expect } from '@jest/globals';

describe('API Integration Tests', () => {
  it('should check SCADA health', async () => {
    const response = await fetch('http://localhost:3010/api/scada/health');
    const data = await response.json();
    
    expect(response.status).toBe(200);
    expect(data.status).toBeDefined();
    expect(data.gates).toBeDefined();
  });
  
  it('should calculate water demand', async () => {
    const response = await fetch('http://localhost:3047/api/water-demand/zone/weekly', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        zoneId: 'zone-1',
        week: 36,
        year: 2025
      })
    });
    
    const data = await response.json();
    expect(response.status).toBe(200);
    expect(data.waterDemand.total).toBeGreaterThan(0);
  });
});
```

### Postman Collection

Import this collection for API testing:

```json
{
  "info": {
    "name": "Munbon Irrigation API",
    "version": "1.0.0"
  },
  "item": [
    {
      "name": "SCADA Health",
      "request": {
        "method": "GET",
        "url": "{{baseUrl}}/api/scada/health",
        "header": [
          {
            "key": "Authorization",
            "value": "Bearer {{token}}"
          }
        ]
      }
    }
  ],
  "variable": [
    {
      "key": "baseUrl",
      "value": "http://localhost:3010"
    },
    {
      "key": "token",
      "value": "debug-token"
    }
  ]
}
```

---

## FAQ

### Q: How do I handle offline mode?
```javascript
// Implement offline queue
class OfflineQueue {
  constructor() {
    this.queue = [];
  }
  
  add(request) {
    this.queue.push(request);
    localStorage.setItem('offlineQueue', JSON.stringify(this.queue));
  }
  
  async flush() {
    const queue = [...this.queue];
    this.queue = [];
    
    for (const request of queue) {
      try {
        await fetch(request.url, request.options);
      } catch (error) {
        this.add(request); // Re-queue on failure
      }
    }
  }
}
```

### Q: How do I implement optimistic updates?
```javascript
// Optimistic gate control
const controlGateOptimistic = async (gateId, position) => {
  // Update UI immediately
  updateGateUI(gateId, { position, status: 'moving' });
  
  try {
    const result = await controlGate(gateId, position);
    // Confirm with actual result
    updateGateUI(gateId, result);
  } catch (error) {
    // Revert on failure
    revertGateUI(gateId);
    throw error;
  }
};
```

### Q: How do I cache API responses?
```javascript
// Simple cache implementation
class ApiCache {
  constructor(ttl = 60000) { // 1 minute default
    this.cache = new Map();
    this.ttl = ttl;
  }
  
  set(key, data) {
    this.cache.set(key, {
      data,
      expiry: Date.now() + this.ttl
    });
  }
  
  get(key) {
    const item = this.cache.get(key);
    if (!item) return null;
    
    if (Date.now() > item.expiry) {
      this.cache.delete(key);
      return null;
    }
    
    return item.data;
  }
}

const cache = new ApiCache();

const getCachedGateStatus = async (gateId) => {
  const cacheKey = `gate-${gateId}`;
  let data = cache.get(cacheKey);
  
  if (!data) {
    data = await getGateStatus(gateId);
    cache.set(cacheKey, data);
  }
  
  return data;
};
```

### Q: How do I handle concurrent requests?
```javascript
// Request deduplication
const pendingRequests = new Map();

const dedupedFetch = async (url, options) => {
  const key = `${url}-${JSON.stringify(options)}`;
  
  if (pendingRequests.has(key)) {
    return pendingRequests.get(key);
  }
  
  const promise = fetch(url, options)
    .then(res => res.json())
    .finally(() => pendingRequests.delete(key));
  
  pendingRequests.set(key, promise);
  return promise;
};
```

---

## Support & Contact

### Development Support
- Debug Dashboard: http://localhost:9999
- API Documentation: http://localhost:3000/api-docs
- Request Logs: http://localhost:9998

### Production Support
- Status Page: https://status.munbon.th
- API Documentation: https://api.munbon.th/docs
- Support Email: api-support@munbon.th

### Useful Commands
```bash
# Check service logs
docker logs debug-awd-control -f
docker logs debug-ros -f

# Test connectivity
curl http://localhost:3010/health
curl http://localhost:3047/health

# Reset services
docker-compose -f docker-compose.debug.yml restart
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-01-15 | Initial release |

---

## Appendix

### A. Data Types

```typescript
// TypeScript definitions
interface Gate {
  gateId: string;
  name: string;
  position: number; // 0-100
  status: 'online' | 'offline' | 'error';
  mode: 'auto' | 'manual' | 'maintenance';
}

interface WaterDemand {
  value: number;
  unit: 'm³' | 'liters';
  dailyAverage: number;
  peakDay?: {
    date: string;
    demand: number;
  };
}

interface IrrigationSchedule {
  scheduleId: string;
  waterDemand: number;
  duration: number;
  sections: string[];
  autoAdjust: boolean;
}
```

### B. Common Patterns

```javascript
// Polling pattern
const usePolling = (fn, interval = 5000) => {
  useEffect(() => {
    fn();
    const timer = setInterval(fn, interval);
    return () => clearInterval(timer);
  }, [fn, interval]);
};

// Debounce pattern
const useDebounce = (value, delay = 500) => {
  const [debouncedValue, setDebouncedValue] = useState(value);
  
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedValue(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  
  return debouncedValue;
};
```

---

**End of API Manual**

For latest updates and additional resources, visit: https://docs.munbon.th/api