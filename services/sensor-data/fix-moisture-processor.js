// Fixed moisture data processor based on actual payload structure
// Payload format confirmed:
/*
{
  "gw_id": "3",
  "gateway_msg_type": "Interval",
  "gateway_date": "2025/08/02",
  "gateway_utc": "06:54:14",
  "gps_lat": "13.94551",
  "gps_lng": "100.73405",
  "gw_temp": "37.10",
  "gw_himid": "43.40",
  "gw_head_index": "42.87",
  "gw_batt": "12.33",
  "sensor": [{
    "sensor_id": "13",
    "sensor_msg_type": "Interval",
    "sensor_date": "2025/08/02",
    "sensor_utc": "06:51:17",
    "humid_hi": "008",
    "humid_low": "006",
    "temp_hi": "29.00",
    "temp_low": "29.50",
    "amb_humid": "33.7",
    "amb_temp": "38.2",
    "flood": "no",
    "sensor_batt": "404"
  }]
}
*/

// The fixed INSERT query should be:
const fixedQuery = `
  INSERT INTO moisture_readings (
    time,
    sensor_id,
    location_lat,
    location_lng,
    moisture_surface_pct,
    moisture_deep_pct,
    temp_surface_c,
    temp_deep_c,
    ambient_humidity_pct,
    ambient_temp_c,
    voltage,
    flood_status,
    quality_score
  ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
`;

// Fixed field mapping
function processMoistureSensor(sensor, gatewayId, lat, lng, timestamp) {
  // Construct sensor ID: gateway_id + sensor_id
  const fullSensorId = gatewayId.padStart(4, '0') + '-' + sensor.sensor_id.padStart(4, '0');
  
  // Convert voltage from format like "404" to 4.04
  const voltage = sensor.sensor_batt ? parseFloat(sensor.sensor_batt) / 100 : null;
  
  // Convert flood status from "yes"/"no" to boolean
  const floodStatus = sensor.flood === 'yes';
  
  return [
    timestamp,
    fullSensorId,
    lat,
    lng,
    parseFloat(sensor.humid_hi) || null,      // moisture_surface_pct
    parseFloat(sensor.humid_low) || null,     // moisture_deep_pct
    parseFloat(sensor.temp_hi) || null,       // temp_surface_c
    parseFloat(sensor.temp_low) || null,      // temp_deep_c
    parseFloat(sensor.amb_humid) || null,     // ambient_humidity_pct
    parseFloat(sensor.amb_temp) || null,      // ambient_temp_c
    voltage,                                  // voltage
    floodStatus,                              // flood_status
    0.95                                      // quality_score
  ];
}

// Update for simple-http-server.js moisture endpoint:
// Replace lines 67-75 with:
/*
      await dbPool.query(query, [
        timestamp,
        gatewayId.padStart(4, '0') + '-' + (sensor.sensor_id || '').padStart(4, '0'),
        lat,
        lng,
        parseFloat(sensor.humid_hi) || null,
        parseFloat(sensor.humid_low) || null,
        parseFloat(sensor.temp_hi) || null,
        parseFloat(sensor.temp_low) || null,
        parseFloat(sensor.amb_humid) || null,
        parseFloat(sensor.amb_temp) || null,
        sensor.sensor_batt ? parseFloat(sensor.sensor_batt) / 100 : null,
        sensor.flood === 'yes',
        0.95
      ]);
*/

module.exports = { fixedQuery, processMoistureSensor };