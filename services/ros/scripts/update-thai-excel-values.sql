-- Update ETo values to match Thai Excel file: คบ.มูลบน_ROS_ฤดูฝน(2568).xlsm
-- Station: นครราชสีมา

-- Set schema search path
SET search_path TO ros, public;

-- Update monthly ETo values
UPDATE ros.eto_monthly SET eto_value = 121.68 WHERE aos_station = 'นครราชสีมา' AND month = 1;  -- January
UPDATE ros.eto_monthly SET eto_value = 123.94 WHERE aos_station = 'นครราชสีมา' AND month = 2;  -- February
UPDATE ros.eto_monthly SET eto_value = 150.05 WHERE aos_station = 'นครราชสีมา' AND month = 3;  -- March
UPDATE ros.eto_monthly SET eto_value = 147.47 WHERE aos_station = 'นครราชสีมา' AND month = 4;  -- April
UPDATE ros.eto_monthly SET eto_value = 142.65 WHERE aos_station = 'นครราชสีมา' AND month = 5;  -- May
UPDATE ros.eto_monthly SET eto_value = 132.26 WHERE aos_station = 'นครราชสีมา' AND month = 6;  -- June
UPDATE ros.eto_monthly SET eto_value = 137.98 WHERE aos_station = 'นครราชสีมา' AND month = 7;  -- July
UPDATE ros.eto_monthly SET eto_value = 137.58 WHERE aos_station = 'นครราชสีมา' AND month = 8;  -- August
UPDATE ros.eto_monthly SET eto_value = 127.65 WHERE aos_station = 'นครราชสีมา' AND month = 9;  -- September
UPDATE ros.eto_monthly SET eto_value = 119.42 WHERE aos_station = 'นครราชสีมา' AND month = 10; -- October
UPDATE ros.eto_monthly SET eto_value = 106.99 WHERE aos_station = 'นครราชสีมา' AND month = 11; -- November
UPDATE ros.eto_monthly SET eto_value = 114.67 WHERE aos_station = 'นครราชสีมา' AND month = 12; -- December

-- Update Kc values for rice (ข้าว กข.) to match Thai Excel
UPDATE ros.kc_weekly SET kc_value = 1.07 WHERE crop_type = 'rice' AND crop_week = 1;
UPDATE ros.kc_weekly SET kc_value = 0.79 WHERE crop_type = 'rice' AND crop_week = 2;
UPDATE ros.kc_weekly SET kc_value = 1.30 WHERE crop_type = 'rice' AND crop_week = 3;
UPDATE ros.kc_weekly SET kc_value = 0.52 WHERE crop_type = 'rice' AND crop_week = 4;
UPDATE ros.kc_weekly SET kc_value = 0.72 WHERE crop_type = 'rice' AND crop_week = 5;
UPDATE ros.kc_weekly SET kc_value = 0.68 WHERE crop_type = 'rice' AND crop_week = 6;
UPDATE ros.kc_weekly SET kc_value = 0.57 WHERE crop_type = 'rice' AND crop_week = 7;
UPDATE ros.kc_weekly SET kc_value = 0.69 WHERE crop_type = 'rice' AND crop_week = 8;
UPDATE ros.kc_weekly SET kc_value = 0.72 WHERE crop_type = 'rice' AND crop_week = 9;
UPDATE ros.kc_weekly SET kc_value = 0.87 WHERE crop_type = 'rice' AND crop_week = 10;
UPDATE ros.kc_weekly SET kc_value = 0.70 WHERE crop_type = 'rice' AND crop_week = 11;
UPDATE ros.kc_weekly SET kc_value = 0.57 WHERE crop_type = 'rice' AND crop_week = 12;
UPDATE ros.kc_weekly SET kc_value = 0.73 WHERE crop_type = 'rice' AND crop_week = 13;
UPDATE ros.kc_weekly SET kc_value = 1.14 WHERE crop_type = 'rice' AND crop_week = 14;
UPDATE ros.kc_weekly SET kc_value = 0.82 WHERE crop_type = 'rice' AND crop_week = 15;
UPDATE ros.kc_weekly SET kc_value = 0.76 WHERE crop_type = 'rice' AND crop_week = 16;

-- Add additional weeks for rice (17-25) from Thai Excel
INSERT INTO ros.kc_weekly (crop_type, crop_week, kc_value) VALUES 
('rice', 17, 0.82),
('rice', 18, 1.09),
('rice', 19, 1.36),
('rice', 20, 0.60),
('rice', 21, 0.58),
('rice', 22, 0.88),
('rice', 23, 0.65),
('rice', 24, 0.76),
('rice', 25, 0.68)
ON CONFLICT (crop_type, crop_week) 
DO UPDATE SET kc_value = EXCLUDED.kc_value;

-- Update Kc values for corn (ข้าวโพดเลี้ยงสัตว์)
UPDATE ros.kc_weekly SET kc_value = 1.12 WHERE crop_type = 'corn' AND crop_week = 1;
UPDATE ros.kc_weekly SET kc_value = 0.97 WHERE crop_type = 'corn' AND crop_week = 2;
UPDATE ros.kc_weekly SET kc_value = 1.36 WHERE crop_type = 'corn' AND crop_week = 3;
UPDATE ros.kc_weekly SET kc_value = 0.61 WHERE crop_type = 'corn' AND crop_week = 4;
UPDATE ros.kc_weekly SET kc_value = 0.86 WHERE crop_type = 'corn' AND crop_week = 5;
UPDATE ros.kc_weekly SET kc_value = 0.84 WHERE crop_type = 'corn' AND crop_week = 6;
UPDATE ros.kc_weekly SET kc_value = 0.68 WHERE crop_type = 'corn' AND crop_week = 7;
UPDATE ros.kc_weekly SET kc_value = 0.81 WHERE crop_type = 'corn' AND crop_week = 8;
UPDATE ros.kc_weekly SET kc_value = 0.85 WHERE crop_type = 'corn' AND crop_week = 9;
UPDATE ros.kc_weekly SET kc_value = 1.18 WHERE crop_type = 'corn' AND crop_week = 10;
UPDATE ros.kc_weekly SET kc_value = 0.85 WHERE crop_type = 'corn' AND crop_week = 11;
UPDATE ros.kc_weekly SET kc_value = 0.69 WHERE crop_type = 'corn' AND crop_week = 12;
UPDATE ros.kc_weekly SET kc_value = 0.75 WHERE crop_type = 'corn' AND crop_week = 13;
UPDATE ros.kc_weekly SET kc_value = 1.60 WHERE crop_type = 'corn' AND crop_week = 14;
UPDATE ros.kc_weekly SET kc_value = 0.91 WHERE crop_type = 'corn' AND crop_week = 15;
UPDATE ros.kc_weekly SET kc_value = 0.80 WHERE crop_type = 'corn' AND crop_week = 16;

-- Add test area data
INSERT INTO ros.area_info (area_id, area_type, area_name, total_area_rai, aos_station, province) VALUES
('THAI-TEST-01', 'plot', 'Thai Test Plot 1', 100, 'นครราชสีมา', 'นครราชสีมา'),
('THAI-TEST-02', 'plot', 'Thai Test Plot 2', 1000, 'นครราชสีมา', 'นครราชสีมา'),
('MUNBON-PROJECT', 'project', 'โครงการชลประทานมูลบน', 45731, 'นครราชสีมา', 'นครราชสีมา')
ON CONFLICT (area_id) DO NOTHING;

-- Verify the updates
SELECT 'ETo Data for นครราชสีมา:' as info;
SELECT month, eto_value FROM ros.eto_monthly 
WHERE aos_station = 'นครราชสีมา' 
ORDER BY month;

SELECT 'Rice Kc values (first 16 weeks):' as info;
SELECT crop_week, kc_value FROM ros.kc_weekly 
WHERE crop_type = 'rice' AND crop_week <= 16
ORDER BY crop_week;