# Token Structure Documentation

## Current Implementation (Munbon Area Only)

The token structure follows the pattern: `{area}-{manufacturer}-{sensor-type}`

### Current Tokens:
- `munbon-ridr-water-level` - RID-R water level sensors in Munbon area
- `munbon-m2m-moisture` - M2M moisture sensors in Munbon area
- `munbon-test-devices` - Test and development devices

### Manufacturers:
- **RID-R**: Water level sensor manufacturer
- **M2M**: Moisture sensor manufacturer

## Future Expansion

When expanding to other irrigation areas, new tokens will follow the same pattern:

### Example Future Tokens:
```
# Chiang Mai area
chiangmai-ridr-water-level
chiangmai-m2m-moisture

# Khon Kaen area
khonkaen-ridr-water-level
khonkaen-m2m-moisture

# Support for new manufacturers
munbon-newbrand-water-level
munbon-otherbrand-moisture
```

## Token Validation

Tokens serve multiple purposes:
1. **Authentication**: Verify device is authorized
2. **Area Identification**: Route data to correct regional system
3. **Manufacturer Tracking**: Support different data formats
4. **Sensor Type**: Determine processing logic

## MQTT Topic Structure

Topics follow the pattern: `sensors/{sensor-type}/{area}/{device-id}/{data-type}`

### Examples:
```
sensors/water-level/munbon/ridr-001/data
sensors/water-level/munbon/ridr-001/status
sensors/moisture/munbon/m2m-gw-001-01/data
sensors/moisture/munbon/m2m-gw-001-01/status
```

## Implementation Notes

1. **Area Code**: Use lowercase, no spaces (e.g., `munbon`, `chiangmai`)
2. **Manufacturer**: Use lowercase manufacturer code
3. **Sensor Type**: Use hyphenated lowercase (e.g., `water-level`, `moisture`)
4. **Validation**: Tokens are validated at API Gateway and MQTT broker levels
5. **Configuration**: Tokens are configured via environment variables

## Security Considerations

1. Tokens should be kept secret and rotated periodically
2. Use HTTPS/TLS for all communications
3. Implement rate limiting per token
4. Monitor for unusual activity per token
5. Consider implementing token expiration for enhanced security