-- Add monthly effective rainfall table to ROS schema
-- Based on Thai Excel sheet: ฝนใช้การรายวัน

SET search_path TO ros, public;

-- Create monthly effective rainfall table
CREATE TABLE IF NOT EXISTS ros.effective_rainfall_monthly (
    id SERIAL PRIMARY KEY,
    aos_station VARCHAR(100) NOT NULL DEFAULT 'นครราชสีมา',
    province VARCHAR(100) NOT NULL DEFAULT 'นครราชสีมา',
    month INTEGER NOT NULL CHECK (month >= 1 AND month <= 12),
    crop_type VARCHAR(50) NOT NULL, -- 'rice' or 'field_crop'
    effective_rainfall_mm DECIMAL(10,2) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(aos_station, province, month, crop_type)
);

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_effective_rainfall_monthly 
ON ros.effective_rainfall_monthly(aos_station, province, month, crop_type);

-- Insert effective rainfall data for rice
INSERT INTO ros.effective_rainfall_monthly (aos_station, province, month, crop_type, effective_rainfall_mm)
VALUES 
    ('นครราชสีมา', 'นครราชสีมา', 1, 'rice', 4.6),
    ('นครราชสีมา', 'นครราชสีมา', 2, 'rice', 20.5),
    ('นครราชสีมา', 'นครราชสีมา', 3, 'rice', 41.6),
    ('นครราชสีมา', 'นครราชสีมา', 4, 'rice', 65.8),
    ('นครราชสีมา', 'นครราชสีมา', 5, 'rice', 152.1),
    ('นครราชสีมา', 'นครราชสีมา', 6, 'rice', 104.5),
    ('นครราชสีมา', 'นครราชสีมา', 7, 'rice', 122.5),
    ('นครราชสีมา', 'นครราชสีมา', 8, 'rice', 128.0),
    ('นครราชสีมา', 'นครราชสีมา', 9, 'rice', 233.2),
    ('นครราชสีมา', 'นครราชสีมา', 10, 'rice', 152.1),
    ('นครราชสีมา', 'นครราชสีมา', 11, 'rice', 31.0),
    ('นครราชสีมา', 'นครราชสีมา', 12, 'rice', 3.6)
ON CONFLICT (aos_station, province, month, crop_type) 
DO UPDATE SET 
    effective_rainfall_mm = EXCLUDED.effective_rainfall_mm,
    updated_at = NOW();

-- Insert effective rainfall data for field crops (corn, sugarcane, etc.)
INSERT INTO ros.effective_rainfall_monthly (aos_station, province, month, crop_type, effective_rainfall_mm)
VALUES 
    ('นครราชสีมา', 'นครราชสีมา', 1, 'field_crop', 4.6),
    ('นครราชสีมา', 'นครราชสีมา', 2, 'field_crop', 16.5),
    ('นครราชสีมา', 'นครราชสีมา', 3, 'field_crop', 31.3),
    ('นครราชสีมา', 'นครราชสีมา', 4, 'field_crop', 42.3),
    ('นครราชสีมา', 'นครราชสีมา', 5, 'field_crop', 67.6),
    ('นครราชสีมา', 'นครราชสีมา', 6, 'field_crop', 46.5),
    ('นครราชสีมา', 'นครราชสีมา', 7, 'field_crop', 74.5),
    ('นครราชสีมา', 'นครราชสีมา', 8, 'field_crop', 89.3),
    ('นครราชสีมา', 'นครราชสีมา', 9, 'field_crop', 142.6),
    ('นครราชสีมา', 'นครราชสีมา', 10, 'field_crop', 81.8),
    ('นครราชสีมา', 'นครราชสีมา', 11, 'field_crop', 21.4),
    ('นครราชสีมา', 'นครราชสีมา', 12, 'field_crop', 3.6)
ON CONFLICT (aos_station, province, month, crop_type) 
DO UPDATE SET 
    effective_rainfall_mm = EXCLUDED.effective_rainfall_mm,
    updated_at = NOW();

-- Add trigger to update updated_at
CREATE OR REPLACE TRIGGER update_effective_rainfall_monthly_updated_at
    BEFORE UPDATE ON ros.effective_rainfall_monthly
    FOR EACH ROW
    EXECUTE FUNCTION ros.update_updated_at_column();

-- Verify data was inserted correctly
SELECT 
    month,
    crop_type,
    effective_rainfall_mm,
    ROUND(effective_rainfall_mm / 4, 2) as weekly_effective_rainfall
FROM ros.effective_rainfall_monthly
WHERE aos_station = 'นครราชสีมา'
ORDER BY crop_type, month;

-- Summary comparison
SELECT 
    crop_type,
    SUM(effective_rainfall_mm) as annual_total,
    ROUND(AVG(effective_rainfall_mm), 2) as monthly_average,
    ROUND(AVG(effective_rainfall_mm) / 4, 2) as weekly_average
FROM ros.effective_rainfall_monthly
WHERE aos_station = 'นครราชสีมา'
GROUP BY crop_type;