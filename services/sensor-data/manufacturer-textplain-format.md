# Moisture Data Format Instructions

## Content-Type: text/plain Support

We understand you cannot set `Content-Type: application/json`. Our endpoint now accepts `Content-Type: text/plain`.

## Correct Format

When sending with `Content-Type: text/plain`, send the **raw JSON without quotes**:

### ✅ CORRECT - Raw JSON (no quotes)
```
{
  "gw_id": "0003",
  "gateway_msg_type": "data",
  "gateway_date": "2025/08/02",
  "gateway_utc": "12:30:00",
  "gps_lat": "14.2333",
  "gps_lng": "99.1234",
  "gw_batt": "450",
  "sensor": [
    {
      "sensor_id": "13",
      "sensor_msg_type": "data",
      "sensor_date": "2025/08/02",
      "sensor_utc": "12:30:00",
      "humid_hi": "35",
      "humid_low": "38",
      "temp_hi": "28.5",
      "temp_low": "27.2",
      "amb_humid": "65",
      "amb_temp": "29.8",
      "flood": "no",
      "sensor_batt": "420"
    }
  ]
}
```

### ❌ INCORRECT - JSON wrapped in quotes
```
"{\"gw_id\":\"0003\",\"gateway_msg_type\":\"data\"...}"
```

## Test Examples

### Using curl with text/plain
```bash
curl -X POST http://43.209.22.250:8080/api/sensor-data/moisture/munbon-m2m-moisture \
  -H "Content-Type: text/plain" \
  -d '{
    "gw_id": "0003",
    "gateway_msg_type": "data",
    "gateway_date": "2025/08/02",
    "gateway_utc": "12:30:00",
    "gps_lat": "14.2333",
    "gps_lng": "99.1234",
    "gw_batt": "450",
    "sensor": [{
      "sensor_id": "13",
      "humid_hi": "35",
      "humid_low": "38"
    }]
  }'
```

### Response
```json
{"status":"success","message":"Data received and processed"}
```

## Important Notes

1. **No quotes around JSON** - Send raw JSON object, not a string
2. **Valid JSON required** - Must be properly formatted JSON
3. **Content-Type** - Can be `text/plain` or `application/json`
4. **Special characters** - No newlines inside string values
5. **Encoding** - UTF-8 encoding required

## Common Errors

### Error: Invalid JSON
```json
{
  "status": "error",
  "message": "Invalid JSON in request body",
  "hint": "Send raw JSON without quotes: {\"gw_id\":\"0003\",...}"
}
```
**Fix**: Remove quotes around JSON, ensure valid JSON format

### Error: Bad control character
**Cause**: Newlines or tabs inside string values
**Fix**: Remove all newlines/tabs from inside strings

## Summary

Send your JSON data as:
- **Content-Type**: text/plain ✅
- **Body**: Raw JSON object (no surrounding quotes) ✅
- **Format**: Valid JSON with proper escaping ✅