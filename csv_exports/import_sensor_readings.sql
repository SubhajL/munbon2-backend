-- Clear existing data
TRUNCATE TABLE public.sensor_readings;

-- Disable triggers
ALTER TABLE public.sensor_readings DISABLE TRIGGER ALL;

-- Insert data
INSERT INTO public.sensor_readings (time, sensor_id, sensor_type, location_lat, location_lng, value, metadata, quality_score) VALUES ('2025-06-03 20:41:29.821', '00001-00001', 'moisture', 100.5018, 13.7563, '"{""date"": ""2025/06/03""'::jsonb, ' ""time"": ""20:41:28""'::jsonb,  ""flood"": ""no"", ""temp_hi"": ""28.50"", ""amb_temp"": ""32.50"", ""humid_hi"": ""45"", ""msg_type"": ""interval"", ""temp_low"": ""27.00"", ""amb_humid"": ""65"", ""humid_low"": ""58"", ""sensor_id"": ""00001"", ""gateway_id"": ""00001"", ""sensor_batt"": ""395""}","{""msgType"": ""interval"", ""gatewayId"": ""00001"", ""manufacturer"": ""M2M"", ""sensorBattery"": 3.95, ""gatewayBattery"": 3.72}",1.00);
INSERT INTO public.sensor_readings (time, sensor_id, sensor_type, location_lat, location_lng, value, metadata, quality_score) VALUES ('2025-06-03 20:41:29.821', '00001-00001', 'moisture', 100.5018, 13.7563, '"{""date"": ""2025/06/03""'::jsonb, ' ""time"": ""20:41:28""'::jsonb,  ""flood"": ""no"", ""temp_hi"": ""28.50"", ""amb_temp"": ""32.50"", ""humid_hi"": ""45"", ""msg_type"": ""interval"", ""temp_low"": ""27.00"", ""amb_humid"": ""65"", ""humid_low"": ""58"", ""sensor_id"": ""00001"", ""gateway_id"": ""00001"", ""sensor_batt"": ""395""}","{""msgType"": ""interval"", ""gatewayId"": ""00001"", ""manufacturer"": ""M2M"", ""sensorBattery"": 3.95, ""gatewayBattery"": 3.72}",1.00);
INSERT INTO public.sensor_readings (time, sensor_id, sensor_type, location_lat, location_lng, value, metadata, quality_score) VALUES ('2025-06-03 20:44:03.255', '00001-00001', 'moisture', 100.5018, 13.7563, '"{""date"": ""2025/06/03""'::jsonb, ' ""time"": ""20:44:02""'::jsonb,  ""flood"": ""no"", ""temp_hi"": ""28.50"", ""amb_temp"": ""32.50"", ""humid_hi"": ""45"", ""msg_type"": ""interval"", ""temp_low"": ""27.00"", ""amb_humid"": ""65"", ""humid_low"": ""58"", ""sensor_id"": ""00001"", ""gateway_id"": ""00001"", ""sensor_batt"": ""395""}","{""msgType"": ""interval"", ""gatewayId"": ""00001"", ""manufacturer"": ""M2M"", ""sensorBattery"": 3.95, ""gatewayBattery"": 3.72}",1.00);
-- Re-enable triggers
ALTER TABLE public.sensor_readings ENABLE TRIGGER ALL;
-- Verify
SELECT COUNT(*) FROM public.sensor_readings;
