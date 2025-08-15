-- Create weekly ETo table to store week-specific values from Excel
CREATE TABLE IF NOT EXISTS ros.eto_weekly (
    id SERIAL PRIMARY KEY,
    aos_station VARCHAR(100) NOT NULL DEFAULT 'นครราชสีมา',
    province VARCHAR(100) NOT NULL DEFAULT 'นครราชสีมา',
    calendar_week INTEGER NOT NULL CHECK (calendar_week >= 1 AND calendar_week <= 53),
    calendar_year INTEGER NOT NULL,
    month INTEGER NOT NULL CHECK (month >= 1 AND month <= 12),
    eto_value NUMERIC(10,2) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(aos_station, province, calendar_week, calendar_year)
);

-- Create index for efficient queries
CREATE INDEX idx_eto_weekly_lookup ON ros.eto_weekly(aos_station, province, calendar_week, calendar_year);
CREATE INDEX idx_eto_weekly_year_week ON ros.eto_weekly(calendar_year, calendar_week);

-- Add update trigger
CREATE TRIGGER update_eto_weekly_updated_at 
    BEFORE UPDATE ON ros.eto_weekly 
    FOR EACH ROW 
    EXECUTE FUNCTION ros.update_updated_at_column();

-- Insert weekly ETo values from Excel for 2024
-- Based on the Excel spreadsheet showing weekly-specific ETo values
-- Starting from week 18 (early May) as shown in Excel
INSERT INTO ros.eto_weekly (aos_station, province, calendar_week, calendar_year, month, eto_value) VALUES
-- May weeks (พ.ค.)
('นครราชสีมา', 'นครราชสีมา', 18, 2024, 5, 48.13),
('นครราชสีมา', 'นครราชสีมา', 19, 2024, 5, 48.77),
('นครราชสีมา', 'นครราชสีมา', 20, 2024, 5, 49.44),
('นครราชสีมา', 'นครราชสีมา', 21, 2024, 5, 51.02),
-- June weeks (มิ.ย.) 
('นครราชสีมา', 'นครราชสีมา', 22, 2024, 6, 51.26),
('นครราชสีมา', 'นครราชสีมา', 23, 2024, 6, 51.42),
('นครราชสีมา', 'นครราชสีมา', 24, 2024, 6, 48.87),
('นครราชสีมา', 'นครราชสีมา', 25, 2024, 6, 46.73),
-- July weeks (ก.ค.)
('นครราชสีมา', 'นครราชสีมา', 26, 2024, 7, 43.36),
('นครราชสีมา', 'นครราชสีมา', 27, 2024, 7, 42.77),
('นครราชสีมา', 'นครราชสีมา', 28, 2024, 7, 33.13),  -- This is our July planting start
('นครราชสีมา', 'นครราชสีมา', 29, 2024, 7, 33.13),
('นครราชสีมา', 'นครราชสีมา', 30, 2024, 7, 33.13),
-- August weeks (ส.ค.)
('นครราชสีมา', 'นครราชสีมา', 31, 2024, 8, 31.04),
('นครราชสีมา', 'นครราชสีมา', 32, 2024, 8, 31.04),
('นครราชสีมา', 'นครราชสีมา', 33, 2024, 8, 31.04),
('นครราชสีมา', 'นครราชสีมา', 34, 2024, 8, 31.04),
-- September weeks (ก.ย.)
('นครราชสีมา', 'นครราชสีมา', 35, 2024, 9, 28.50),
('นครราชสีมา', 'นครราชสีมา', 36, 2024, 9, 28.50),
('นครราชสีมา', 'นครราชสีมา', 37, 2024, 9, 28.50),
('นครราชสีมา', 'นครราชสีมา', 38, 2024, 9, 28.50),
('นครราชสีมา', 'นครราชสีมา', 39, 2024, 9, 28.50),
-- October weeks (ต.ค.)
('นครราชสีมา', 'นครราชสีมา', 40, 2024, 10, 29.41),
('นครราชสีมา', 'นครราชสีมา', 41, 2024, 10, 29.41),
('นครราชสีมา', 'นครราชสีมา', 42, 2024, 10, 29.41),
('นครราชสีมา', 'นครราชสีมา', 43, 2024, 10, 29.41),
-- November weeks (พ.ย.)
('นครราชสีมา', 'นครราชสีมา', 44, 2024, 11, 26.34),
('นครราชสีมา', 'นครราชสีมา', 45, 2024, 11, 26.34),
('นครราชสีมา', 'นครราชสีมา', 46, 2024, 11, 26.34),
('นครราชสีมา', 'นครราชสีมา', 47, 2024, 11, 26.34);

-- Add values for other months to complete the year
-- January weeks
INSERT INTO ros.eto_weekly (aos_station, province, calendar_week, calendar_year, month, eto_value)
SELECT 'นครราชสีมา', 'นครราชสีมา', week, 2024, 1, 26.23
FROM generate_series(1, 4) AS week;

-- February weeks  
INSERT INTO ros.eto_weekly (aos_station, province, calendar_week, calendar_year, month, eto_value)
SELECT 'นครราชสีมา', 'นครราชสีมา', week, 2024, 2, 28.60
FROM generate_series(5, 8) AS week;

-- March weeks
INSERT INTO ros.eto_weekly (aos_station, province, calendar_week, calendar_year, month, eto_value)
SELECT 'นครราชสีมา', 'นครราชสีมา', week, 2024, 3, 37.15
FROM generate_series(9, 13) AS week;

-- April weeks
INSERT INTO ros.eto_weekly (aos_station, province, calendar_week, calendar_year, month, eto_value)
SELECT 'นครราชสีมา', 'นครราชสีมา', week, 2024, 4, 38.11
FROM generate_series(14, 17) AS week;

-- December weeks
INSERT INTO ros.eto_weekly (aos_station, province, calendar_week, calendar_year, month, eto_value)
SELECT 'นครราชสีมา', 'นครราชสีมา', week, 2024, 12, 25.15
FROM generate_series(48, 52) AS week;

-- Verify the data
SELECT 
    calendar_week,
    calendar_year,
    month,
    eto_value,
    CASE month
        WHEN 1 THEN 'ม.ค.'
        WHEN 2 THEN 'ก.พ.'
        WHEN 3 THEN 'มี.ค.'
        WHEN 4 THEN 'เม.ย.'
        WHEN 5 THEN 'พ.ค.'
        WHEN 6 THEN 'มิ.ย.'
        WHEN 7 THEN 'ก.ค.'
        WHEN 8 THEN 'ส.ค.'
        WHEN 9 THEN 'ก.ย.'
        WHEN 10 THEN 'ต.ค.'
        WHEN 11 THEN 'พ.ย.'
        WHEN 12 THEN 'ธ.ค.'
    END as month_thai
FROM ros.eto_weekly
WHERE calendar_year = 2024
ORDER BY calendar_week
LIMIT 20;