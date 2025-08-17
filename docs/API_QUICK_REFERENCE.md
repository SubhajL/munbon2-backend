# API Quick Reference Card
## Munbon Irrigation Control System

### 🔗 Base URLs
```javascript
const API = {
  AWD: 'http://localhost:3010',  // Gate control
  ROS: 'http://localhost:3047',  // Water demand
  AUTH: 'Bearer debug-token'      // Dev token
}
```

---

## 🔍 SCADA Status

### Health Check
```javascript
GET ${API.AWD}/api/scada/health
```

### Gate Status
```javascript
// Single gate
GET ${API.AWD}/api/scada/gates/MG-01/status

// All gates
GET ${API.AWD}/api/scada/gates/status
```

---

## 💧 Water Demand

### Weekly Demand
```javascript
// By Section
POST ${API.ROS}/api/water-demand/section/weekly
{
  "sectionId": "section-1A",
  "week": 36,
  "year": 2025
}

// By Zone
POST ${API.ROS}/api/water-demand/zone/weekly
{
  "zoneId": "zone-1",
  "week": 36,
  "year": 2025
}
```

### Seasonal Demand
```javascript
POST ${API.ROS}/api/water-demand/seasonal
{
  "zoneId": "zone-1",
  "cropType": "rice",
  "plantingDate": "2025-06-15"
}
```

### Current Demand
```javascript
GET ${API.ROS}/api/water-demand/current?level=zone&id=zone-1
```

---

## 🚪 Gate Control

### Single Gate
```javascript
POST ${API.AWD}/api/scada/gates/MG-01/control
{
  "command": "set_position",
  "position": 75,  // 0-100%
  "mode": "manual",
  "reason": "Irrigation"
}
```

### Multiple Gates
```javascript
POST ${API.AWD}/api/scada/gates/batch-control
{
  "gates": [
    {"gateId": "MG-01", "position": 100, "priority": 1},
    {"gateId": "MG-02", "position": 75, "priority": 2}
  ],
  "mode": "sequential",
  "reason": "Zone irrigation"
}
```

### Emergency Stop
```javascript
POST ${API.AWD}/api/scada/gates/emergency-stop
{
  "reason": "Emergency",
  "zones": ["zone-1", "zone-2"],
  "notifyOperators": true
}
```

---

## 🌊 Irrigation Schedule

### Execute Schedule
```javascript
POST ${API.AWD}/api/irrigation/execute-schedule
{
  "scheduleId": "daily-zone-1",
  "waterDemand": 12500,      // m³
  "duration": 14400,          // seconds
  "sections": ["section-1A"],
  "autoAdjust": true
}
```

### Check Status
```javascript
GET ${API.AWD}/api/irrigation/status/{executionId}
```

### Stop Execution
```javascript
POST ${API.AWD}/api/irrigation/stop/{executionId}
{
  "reason": "Manual stop"
}
```

---

## 🔄 WebSocket Updates

### Gate Updates
```javascript
const ws = new WebSocket('ws://localhost:3010/ws/gates');
ws.onmessage = (e) => {
  const data = JSON.parse(e.data);
  // {gateId, position, status, flow}
};
```

### Demand Updates
```javascript
const ws = new WebSocket('ws://localhost:3047/ws/demand');
ws.onmessage = (e) => {
  const data = JSON.parse(e.data);
  // {zoneId, currentDemand, efficiency}
};
```

---

## 📝 Common Patterns

### API Helper
```javascript
async function api(url, options = {}) {
  const res = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'Authorization': API.AUTH,
      ...options.headers
    }
  });
  if (!res.ok) throw new Error(`${res.status}`);
  return res.json();
}
```

### React Hook
```javascript
function useGateStatus(gateId) {
  const [status, setStatus] = useState(null);
  
  useEffect(() => {
    const fetchStatus = async () => {
      const data = await api(`${API.AWD}/api/scada/gates/${gateId}/status`);
      setStatus(data);
    };
    
    fetchStatus();
    const interval = setInterval(fetchStatus, 5000);
    return () => clearInterval(interval);
  }, [gateId]);
  
  return status;
}
```

### Error Handling
```javascript
try {
  const result = await api(url, options);
  // Success
} catch (error) {
  if (error.message === '401') {
    // Refresh token
  } else if (error.message === '429') {
    // Rate limited - retry later
  } else {
    // Other error
  }
}
```

---

## 🎯 Complete Flow Example

```javascript
async function irrigateZone(zoneId) {
  // 1. Check SCADA
  const health = await api(`${API.AWD}/api/scada/health`);
  if (health.status !== 'connected') throw new Error('SCADA offline');
  
  // 2. Calculate demand
  const demand = await api(`${API.ROS}/api/water-demand/zone/weekly`, {
    method: 'POST',
    body: JSON.stringify({
      zoneId,
      week: getCurrentWeek(),
      year: new Date().getFullYear()
    })
  });
  
  // 3. Execute irrigation
  const execution = await api(`${API.AWD}/api/irrigation/execute-schedule`, {
    method: 'POST',
    body: JSON.stringify({
      scheduleId: `${zoneId}-${Date.now()}`,
      waterDemand: demand.waterDemand.total,
      duration: 14400,
      sections: demand.sections.map(s => s.sectionId),
      autoAdjust: true
    })
  });
  
  return execution.executionId;
}
```

---

## 🚨 HTTP Status Codes

| Code | Meaning | Action |
|------|---------|--------|
| 200 | Success | ✓ Process |
| 400 | Bad Request | Check params |
| 401 | Unauthorized | Refresh token |
| 404 | Not Found | Check ID |
| 429 | Rate Limited | Wait & retry |
| 500 | Server Error | Retry later |
| 503 | Unavailable | Service down |

---

## 🛠 Debug Tools

- **Dashboard**: http://localhost:9999
- **Logs**: http://localhost:9998
- **Test Script**: `./test-scada-ros-endpoints.sh`

---

## 📞 Quick Commands

```bash
# Check services
docker ps | grep -E "awd|ros"

# View logs
docker logs debug-awd-control -f
docker logs debug-ros -f

# Test endpoints
curl localhost:3010/api/scada/health
curl localhost:3047/api/water-demand/current

# Restart services
docker restart debug-awd-control debug-ros
```

---

**Version 1.0** | **Date: 2025-01-15** | **Support: backend-team@munbon.th**