# JSON Format Errors from Gateway

## Issue Found
Your gateway (IP: 1.46.20.231) is sending malformed JSON that cannot be parsed. Here are the specific errors:

### Error 1: Bad control character in string literal
- **Position**: 102, 166
- **Meaning**: Your JSON contains unescaped special characters (newlines, tabs, etc.)
- **Example of incorrect format**:
```json
{
  "gw_id": "3
  ",  // <- Newline inside string is not allowed
  "sensor": [...]
}
```

### Error 2: Expected property name or '}' 
- **Position**: 1 (start of JSON)
- **Meaning**: Your JSON doesn't start correctly
- **Example of incorrect format**:
```json
, "gw_id": "3"  // <- Starting with comma
```

## Correct JSON Format Required

```json
{
  "gw_id": "0003",
  "gateway_msg_type": "data",
  "gateway_date": "2025/08/02",
  "gateway_utc": "04:53:47",
  "gps_lat": "14.2333",
  "gps_lng": "99.1234",
  "gw_batt": "450",
  "sensor": [
    {
      "sensor_id": "13",
      "sensor_msg_type": "data",
      "sensor_date": "2025/08/02",
      "sensor_utc": "04:53:47",
      "humid_hi": "16",
      "humid_low": "16",
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

## How to Fix

1. **Remove all newlines/tabs from inside string values**
2. **Ensure JSON starts with `{` not a comma**
3. **Validate JSON before sending** using:
   - Online validator: https://jsonlint.com/
   - Command line: `echo '<your json>' | jq .`

## Test Your Fix

After fixing, test with:
```bash
curl -X POST http://43.209.22.250:8080/api/sensor-data/moisture/munbon-m2m-moisture \
  -H "Content-Type: application/json" \
  -d '<your corrected JSON>'
```

You should receive:
```json
{"status":"success","message":"Data received and processed"}
```