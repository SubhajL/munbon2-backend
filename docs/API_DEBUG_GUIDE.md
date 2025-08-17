# 🔧 API Debug Guide for Frontend Developers

## Quick Start

```bash
# Start the debug server (one command)
./scripts/debug-server.sh

# Everything will be available at:
# - API Gateway: http://localhost:3000
# - Debug Dashboard: http://localhost:9999
# - Request Viewer: http://localhost:9998
```

## 🚀 Key Features for Frontend Debugging

### 1. CORS is COMPLETELY OPEN
```javascript
// No CORS errors - guaranteed!
fetch('http://localhost:3000/api/anything')
  .then(res => res.json())
  .then(data => console.log(data))
```

### 2. Debug Token (No Auth Required)
```javascript
// Use this token for all requests
const DEBUG_TOKEN = 'debug-token';

fetch('http://localhost:3000/api/protected', {
  headers: {
    'Authorization': `Bearer ${DEBUG_TOKEN}`
  }
})
```

### 3. Request/Response Logging
- **EVERY** request is logged with full details
- View at: http://localhost:9998
- See request body, response, headers, timing

### 4. Mock Data Generation
```javascript
// Get mock sensor data
fetch('http://localhost:3003/debug/mock-data?type=sensor&count=100')

// Get mock water level data
fetch('http://localhost:3003/debug/mock-data?type=water-level&count=50')

// Get mock GIS parcels
fetch('http://localhost:3007/debug/mock-parcels?count=20')
```

## 📡 API Endpoints

### Authentication (Port 3001)

#### Debug Login (No Password Required)
```javascript
// POST /auth/debug/login
fetch('http://localhost:3001/auth/debug/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    username: 'test'  // Any username works
  })
})
.then(res => res.json())
.then(data => {
  console.log(data.token);  // Use this token
});
```

#### Get Debug Token
```javascript
// GET /auth/debug/token
fetch('http://localhost:3001/auth/debug/token')
  .then(res => res.json())
  .then(data => console.log(data.token));
```

### Sensor Data (Port 3003)

#### Get Recent Sensor Data
```javascript
// GET /api/sensors/recent
fetch('http://localhost:3003/api/sensors/recent', {
  headers: { 'Authorization': 'Bearer debug-token' }
})
```

#### Get Water Level Data
```javascript
// GET /api/water-level/latest
fetch('http://localhost:3003/api/water-level/latest')
```

#### Get Moisture Data
```javascript
// GET /api/moisture/latest
fetch('http://localhost:3003/api/moisture/latest')
```

#### Post Sensor Data (Testing)
```javascript
// POST /api/sensors/data
fetch('http://localhost:3003/api/sensors/data', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': 'debug-token'
  },
  body: JSON.stringify({
    sensorId: 'TEST-001',
    timestamp: new Date(),
    value: 42.5,
    type: 'temperature'
  })
})
```

### GIS Service (Port 3007)

#### Get Parcels
```javascript
// GET /api/parcels
fetch('http://localhost:3007/api/parcels')
```

#### Get Parcel by Location
```javascript
// GET /api/parcels/at-point
fetch('http://localhost:3007/api/parcels/at-point?lat=13.7563&lng=100.5018')
```

#### Upload Shapefile (Mock)
```javascript
// POST /api/parcels/upload
const formData = new FormData();
formData.append('file', fileInput.files[0]);

fetch('http://localhost:3007/api/parcels/upload', {
  method: 'POST',
  body: formData
})
```

### ROS Service (Port 3047)

#### Calculate Water Demand
```javascript
// POST /api/water-demand/calculate
fetch('http://localhost:3047/api/water-demand/calculate', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    plotId: 'PLOT-001',
    cropType: 'rice',
    area: 100,
    plantingDate: '2024-01-01'
  })
})
```

#### Get Irrigation Schedule
```javascript
// GET /api/schedule/weekly
fetch('http://localhost:3047/api/schedule/weekly?week=36')
```

## 🔍 Debug Dashboard Features

### Access: http://localhost:9999

1. **Service Health Monitor**
   - Real-time health status of all services
   - Green = Healthy, Red = Down
   - Shows last check time and errors

2. **API Tester**
   - Test any endpoint directly from browser
   - Automatic token injection
   - See full request/response

3. **Request Logs**
   - Live stream of all API calls
   - Filter by service, status, or text
   - Export logs as JSON

4. **Mock Data Generator**
   - Generate test data on demand
   - Multiple data types available
   - Copy JSON directly

## 🎯 Common Integration Scenarios

### 1. Login Flow
```javascript
async function debugLogin() {
  // 1. Login
  const loginRes = await fetch('http://localhost:3001/auth/debug/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: 'test-user' })
  });
  
  const { token } = await loginRes.json();
  
  // 2. Use token for protected endpoints
  const dataRes = await fetch('http://localhost:3003/api/sensors/recent', {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  
  return await dataRes.json();
}
```

### 2. Real-time Data Streaming
```javascript
// WebSocket connection for real-time updates
const ws = new WebSocket('ws://localhost:3003/ws');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Real-time data:', data);
};

// Send mock data every 5 seconds
setInterval(() => {
  ws.send(JSON.stringify({
    type: 'sensor-reading',
    sensorId: 'TEST-001',
    value: Math.random() * 100
  }));
}, 5000);
```

### 3. File Upload
```javascript
async function uploadFile(file) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('type', 'shapefile');
  
  const response = await fetch('http://localhost:3007/api/upload', {
    method: 'POST',
    headers: {
      'Authorization': 'Bearer debug-token'
    },
    body: formData
  });
  
  // Check upload progress in Request Viewer
  return await response.json();
}
```

## 🐛 Troubleshooting

### Issue: CORS Error
```javascript
// This should NEVER happen in debug mode
// If it does, check:
// 1. Service is running: docker ps | grep debug-
// 2. Using correct port
// 3. ENV has CORS_ORIGIN=*
```

### Issue: 401 Unauthorized
```javascript
// Solution: Use debug token
headers: {
  'Authorization': 'Bearer debug-token'
}
```

### Issue: Connection Refused
```bash
# Check if services are running
docker ps

# Restart specific service
docker restart debug-sensor-data

# View service logs
docker logs debug-sensor-data -f
```

### Issue: Slow Response
```javascript
// Check the Request Viewer for timing
// http://localhost:9998
// Look for:
// - SQL query time
// - Network latency
// - Processing time
```

## 📊 Performance Monitoring

### Memory Usage
```bash
# View in Debug Dashboard
http://localhost:9999

# Or check console logs
docker logs debug-sensor-data | grep Memory
```

### Request Timing
```javascript
// All requests show timing
console.time('api-call');
fetch('http://localhost:3000/api/endpoint')
  .then(res => {
    console.timeEnd('api-call');
    // Also visible in Request Viewer
  });
```

## 🎨 Testing Different Scenarios

### 1. High Load
```javascript
// Generate 100 concurrent requests
for (let i = 0; i < 100; i++) {
  fetch(`http://localhost:3003/api/sensors/data`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      sensorId: `LOAD-TEST-${i}`,
      value: Math.random() * 100
    })
  });
}
```

### 2. Error Scenarios
```javascript
// Trigger 400 error
fetch('http://localhost:3003/api/invalid-endpoint')

// Trigger 500 error
fetch('http://localhost:3003/debug/trigger-error')

// Trigger timeout
fetch('http://localhost:3003/debug/slow-response?delay=10000')
```

### 3. Different Data Formats
```javascript
// JSON
fetch('http://localhost:3003/api/data.json')

// CSV
fetch('http://localhost:3003/api/data.csv')

// Binary (files)
fetch('http://localhost:3003/api/file.pdf')
```

## 💡 Pro Tips

1. **Use Debug Dashboard** - Don't rely on console.log, use http://localhost:9999
2. **Watch Request Viewer** - See EXACTLY what backend receives/sends
3. **Mock Everything** - Use mock endpoints for faster development
4. **Check Health First** - Always verify services are healthy before debugging
5. **Export Logs** - Save logs for later analysis
6. **Use Debug Tokens** - Skip authentication complexity during development

## 🛠 Useful Browser Extensions

1. **ModHeader** - Automatically add debug token to all requests
2. **JSON Viewer** - Better JSON formatting
3. **Postman** - Import this collection: http://localhost:9999/postman-collection.json

## 📞 Need Help?

1. Check Debug Dashboard: http://localhost:9999
2. View Request Logs: http://localhost:9998
3. Service Logs: `docker logs debug-<service> -f`
4. Restart Everything: `docker-compose -f docker-compose.debug.yml restart`

---

## Quick Copy-Paste Examples

### Fetch with All Headers
```javascript
fetch('http://localhost:3000/api/endpoint', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer debug-token',
    'X-Request-ID': Date.now().toString(),
    'X-Client': 'frontend-debug'
  },
  body: JSON.stringify({ data: 'test' })
})
.then(res => res.json())
.then(console.log)
.catch(console.error);
```

### Axios with Interceptors
```javascript
import axios from 'axios';

// Setup
axios.defaults.baseURL = 'http://localhost:3000';
axios.defaults.headers.common['Authorization'] = 'Bearer debug-token';

// Request interceptor
axios.interceptors.request.use(request => {
  console.log('Starting Request:', request);
  return request;
});

// Response interceptor
axios.interceptors.response.use(
  response => {
    console.log('Response:', response);
    return response;
  },
  error => {
    console.error('Error:', error.response);
    return Promise.reject(error);
  }
);
```

### React Hook Example
```javascript
import { useState, useEffect } from 'react';

function useDebugAPI(endpoint) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  useEffect(() => {
    fetch(`http://localhost:3000${endpoint}`, {
      headers: { 'Authorization': 'Bearer debug-token' }
    })
    .then(res => res.json())
    .then(setData)
    .catch(setError)
    .finally(() => setLoading(false));
  }, [endpoint]);
  
  return { data, loading, error };
}
```

Happy Debugging! 🚀