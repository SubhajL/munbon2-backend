-- Register water level sensor with MAC Address 16186C1FB7E6
INSERT INTO sensor_registry (
    sensor_id,
    sensor_type,
    manufacturer,
    model,
    installation_date,
    last_seen,
    location_lat,
    location_lng,
    metadata,
    is_active,
    created_at,
    updated_at
) VALUES (
    '16186C1FB7E6',
    'water_level',
    'RID-R',
    'AWD-Series',
    '2025-07-01',
    '2025-07-02 13:53:07',
    17.1808429,
    104.1189304,
    '{"name": "AWD Water Level Sensor B7E6", "zone": "Zone1", "deviceId": "AWD-B7E6"}',
    true,
    NOW(),
    NOW()
);

-- You can execute this with:
-- docker exec munbon-timescaledb psql -U postgres -d sensor_data -f /path/to/this/file.sql