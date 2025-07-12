# Munbon API Client Integration Guide

This guide shows how to integrate with Munbon APIs to retrieve water level, moisture, weather data, and upload SHAPE files.

## 🔑 Authentication

All APIs require authentication:
- **Sensor Data APIs**: Header `X-API-Key: your-api-key`
- **SHAPE File Upload**: Header `Authorization: Bearer munbon-ridms-shape`

## 📊 Sensor Data APIs

### Base URL
```
https://your-api-domain.com/api/v1/public
```

### 1. Water Level Data

#### Get Latest Water Levels
```bash
GET /water-levels/latest
```

**Example Request:**
```bash
curl -H "X-API-Key: your-api-key" \
  https://api.munbon.com/api/v1/public/water-levels/latest
```

**Example Response:**
```json
{
  "data_type": "water_level",
  "request_time": "2024-12-26T10:30:00Z",
  "request_time_buddhist": "26/12/2567",
  "sensor_count": 5,
  "sensors": [
    {
      "sensor_id": "wl001",
      "sensor_name": "คลองส่งน้ำสาย 1",
      "location": {
        "longitude": 102.1234,
        "latitude": 14.5678
      },
      "zone": "Zone 1",
      "latest_reading": {
        "timestamp": "2024-12-26T10:00:00Z",
        "timestamp_buddhist": "26/12/2567",
        "water_level_m": 12.5,
        "flow_rate_m3s": 1.2,
        "quality": 100
      }
    }
  ]
}
```

#### Get Historical Data
```bash
GET /water-levels/timeseries?date=26/12/2568
```
Note: Date must be in Buddhist calendar format (DD/MM/YYYY)

### 2. Moisture Data

#### Get Latest Moisture Readings
```bash
GET /moisture/latest
```

**Example Response:**
```json
{
  "data_type": "moisture",
  "request_time": "2024-12-26T10:30:00Z",
  "request_time_buddhist": "26/12/2567",
  "sensor_count": 10,
  "sensors": [
    {
      "sensor_id": "m001",
      "sensor_name": "แปลงนา A1",
      "location": {
        "longitude": 102.1234,
        "latitude": 14.5678
      },
      "zone": "Zone 1",
      "latest_reading": {
        "timestamp": "2024-12-26T10:00:00Z",
        "timestamp_buddhist": "26/12/2567",
        "moisture_percentage": 65.5,
        "temperature_celsius": 28.3,
        "quality": 100
      }
    }
  ]
}
```

### 3. Weather (AOS) Data

#### Get Latest Weather Data
```bash
GET /aos/latest
```

**Example Response:**
```json
{
  "data_type": "aos_meteorological",
  "request_time": "2024-12-26T10:30:00Z",
  "request_time_buddhist": "26/12/2567",
  "station_count": 3,
  "stations": [
    {
      "station_id": "aos001",
      "station_name": "สถานีตรวจอากาศมูลบน",
      "location": {
        "longitude": 102.1234,
        "latitude": 14.5678
      },
      "zone": "Zone 1",
      "latest_reading": {
        "timestamp": "2024-12-26T10:00:00Z",
        "timestamp_buddhist": "26/12/2567",
        "rainfall_mm": 2.5,
        "temperature_celsius": 28.5,
        "humidity_percentage": 75,
        "wind_speed_ms": 3.2,
        "wind_direction_degrees": 180,
        "pressure_hpa": 1013.25
      }
    }
  ]
}
```

## 📁 SHAPE File APIs

### Base URL
```
https://your-rid-api-domain.com
```

### 1. Upload SHAPE File

```bash
POST /api/external/shapefile/push
```

**Headers:**
```
Authorization: Bearer munbon-ridms-shape
Content-Type: application/json
```

**Request Body:**
```json
{
  "filename": "zone1_parcels_2024.zip",
  "content": "base64-encoded-zip-content",
  "metadata": {
    "source": "RID-MS",
    "zone": "Zone 1",
    "uploadDate": "2024-12-26"
  }
}
```

**Example using Python:**
```python
import requests
import base64

# Read and encode ZIP file
with open('parcels.zip', 'rb') as f:
    zip_content = base64.b64encode(f.read()).decode('utf-8')

# Upload
response = requests.post(
    'https://api.munbon.com/api/external/shapefile/push',
    headers={
        'Authorization': 'Bearer munbon-ridms-shape',
        'Content-Type': 'application/json'
    },
    json={
        'filename': 'parcels.zip',
        'content': zip_content,
        'metadata': {
            'source': 'RID-MS',
            'zone': 'Zone 1'
        }
    }
)

print(response.json())
```

### 2. Query Parcel Data

#### List All Shape Files
```bash
GET /api/v1/rid-ms/shapefiles
```

#### Get Parcels by Zone
```bash
GET /api/v1/rid-ms/zones/Zone1/parcels
```

**Example Response:**
```json
{
  "zone": "Zone 1",
  "parcels": [
    {
      "parcelId": "PARCEL-001",
      "areaRai": 25.5,
      "cropType": "Rice",
      "wateringMethod": "Flooding",
      "owner": "นายสมชาย ใจดี",
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[102.123, 14.456], ...]]
      }
    }
  ],
  "totalParcels": 1234,
  "totalAreaRai": 15678.45
}
```

#### Get Water Demand Summary
```bash
GET /api/v1/rid-ms/zones/Zone1/water-demand-summary
```

#### Export as GeoJSON
```bash
GET /api/v1/rid-ms/shapefiles/{shapefileId}/geojson
```

## 💻 Client Code Examples

### Python Client
```python
import requests
from datetime import datetime

class MunbonAPIClient:
    def __init__(self, base_url, api_key):
        self.base_url = base_url
        self.api_key = api_key
        self.headers = {'X-API-Key': api_key}
    
    def get_water_levels_latest(self):
        """Get latest water level readings"""
        url = f"{self.base_url}/api/v1/public/water-levels/latest"
        response = requests.get(url, headers=self.headers)
        return response.json()
    
    def get_moisture_timeseries(self, date_buddhist):
        """Get moisture data for specific date (Buddhist calendar)"""
        url = f"{self.base_url}/api/v1/public/moisture/timeseries"
        params = {'date': date_buddhist}
        response = requests.get(url, headers=self.headers, params=params)
        return response.json()
    
    def get_aos_statistics(self, date_buddhist):
        """Get weather statistics for specific date"""
        url = f"{self.base_url}/api/v1/public/aos/statistics"
        params = {'date': date_buddhist}
        response = requests.get(url, headers=self.headers, params=params)
        return response.json()

# Usage
client = MunbonAPIClient('https://api.munbon.com', 'your-api-key')

# Get latest water levels
water_data = client.get_water_levels_latest()
print(f"Found {water_data['sensor_count']} water level sensors")

# Get today's moisture data (Buddhist calendar)
today_be = datetime.now().strftime('%d/%m/') + str(datetime.now().year + 543)
moisture_data = client.get_moisture_timeseries(today_be)
```

### JavaScript/Node.js Client
```javascript
class MunbonAPIClient {
  constructor(baseUrl, apiKey) {
    this.baseUrl = baseUrl;
    this.apiKey = apiKey;
  }

  async getWaterLevelsLatest() {
    const response = await fetch(`${this.baseUrl}/api/v1/public/water-levels/latest`, {
      headers: { 'X-API-Key': this.apiKey }
    });
    return response.json();
  }

  async getMoistureTimeseries(dateBuddhist) {
    const response = await fetch(
      `${this.baseUrl}/api/v1/public/moisture/timeseries?date=${dateBuddhist}`,
      { headers: { 'X-API-Key': this.apiKey } }
    );
    return response.json();
  }

  async uploadShapefile(filename, base64Content, metadata) {
    const response = await fetch(`${this.baseUrl}/api/external/shapefile/push`, {
      method: 'POST',
      headers: {
        'Authorization': 'Bearer munbon-ridms-shape',
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        filename,
        content: base64Content,
        metadata
      })
    });
    return response.json();
  }
}

// Usage
const client = new MunbonAPIClient('https://api.munbon.com', 'your-api-key');

// Get latest water levels
const waterData = await client.getWaterLevelsLatest();
console.log(`Found ${waterData.sensor_count} sensors`);

// Get moisture data for today (Buddhist calendar)
const today = new Date();
const todayBE = `${today.getDate().toString().padStart(2, '0')}/${(today.getMonth() + 1).toString().padStart(2, '0')}/${today.getFullYear() + 543}`;
const moistureData = await client.getMoistureTimeseries(todayBE);
```

### PHP Client
```php
<?php
class MunbonAPIClient {
    private $baseUrl;
    private $apiKey;
    
    public function __construct($baseUrl, $apiKey) {
        $this->baseUrl = $baseUrl;
        $this->apiKey = $apiKey;
    }
    
    public function getWaterLevelsLatest() {
        $ch = curl_init($this->baseUrl . '/api/v1/public/water-levels/latest');
        curl_setopt($ch, CURLOPT_HTTPHEADER, ['X-API-Key: ' . $this->apiKey]);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        $response = curl_exec($ch);
        curl_close($ch);
        return json_decode($response, true);
    }
    
    public function getMoistureTimeseries($dateBuddhist) {
        $url = $this->baseUrl . '/api/v1/public/moisture/timeseries?date=' . urlencode($dateBuddhist);
        $ch = curl_init($url);
        curl_setopt($ch, CURLOPT_HTTPHEADER, ['X-API-Key: ' . $this->apiKey]);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        $response = curl_exec($ch);
        curl_close($ch);
        return json_decode($response, true);
    }
}

// Usage
$client = new MunbonAPIClient('https://api.munbon.com', 'your-api-key');

// Get water levels
$waterData = $client->getWaterLevelsLatest();
echo "Found " . $waterData['sensor_count'] . " sensors\n";

// Get moisture data for today (Buddhist calendar)
$todayBE = date('d/m/') . (date('Y') + 543);
$moistureData = $client->getMoistureTimeseries($todayBE);
?>
```

## 📈 Rate Limits

- Default: 1000 requests per hour per API key
- Burst: 100 requests per minute
- Contact support for higher limits

## 🔧 Error Handling

All APIs return standard HTTP status codes:
- `200` - Success
- `400` - Bad Request (invalid parameters)
- `401` - Unauthorized (invalid API key)
- `404` - Not Found
- `429` - Too Many Requests (rate limit exceeded)
- `500` - Internal Server Error

Error response format:
```json
{
  "error": "Error message",
  "details": "Additional information"
}
```

## 📞 Support

For API support or additional API keys:
- Email: api-support@munbon-irrigation.th
- Documentation: https://docs.munbon-irrigation.th