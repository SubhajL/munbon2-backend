-- Add ETo values for 2025 crop season (RID weeks 36-48 = Calendar weeks 27-39)
-- These values are taken from Excel for the corresponding calendar weeks

INSERT INTO ros.eto_weekly (aos_station, province, calendar_week, calendar_year, month, eto_value) VALUES
-- July 2025 weeks (ก.ค.)
('นครราชสีมา', 'นครราชสีมา', 27, 2025, 7, 33.13),  -- Crop week 1 (RID week 36)
('นครราชสีมา', 'นครราชสีมา', 28, 2025, 7, 33.13),  -- Crop week 2 (RID week 37)
('นครราชสีมา', 'นครราชสีมา', 29, 2025, 7, 33.13),  -- Crop week 3 (RID week 38)
('นครราชสีมา', 'นครราชสีมา', 30, 2025, 7, 33.13),  -- Crop week 4 (RID week 39)
-- August 2025 weeks (ส.ค.)
('นครราชสีมา', 'นครราชสีมา', 31, 2025, 8, 31.04),  -- Crop week 5 (RID week 40)
('นครราชสีมา', 'นครราชสีมา', 32, 2025, 8, 31.04),  -- Crop week 6 (RID week 41)
('นครราชสีมา', 'นครราชสีมา', 33, 2025, 8, 31.04),  -- Crop week 7 (RID week 42)
('นครราชสีมา', 'นครราชสีมา', 34, 2025, 8, 31.04),  -- Crop week 8 (RID week 43)
-- September 2025 weeks (ก.ย.)
('นครราชสีมา', 'นครราชสีมา', 35, 2025, 9, 28.50),  -- Crop week 9 (RID week 44)
('นครราชสีมา', 'นครราชสีมา', 36, 2025, 9, 28.50),  -- Crop week 10 (RID week 45)
('นครราชสีมา', 'นครราชสีมา', 37, 2025, 9, 28.50),  -- Crop week 11 (RID week 46)
('นครราชสีมา', 'นครราชสีมา', 38, 2025, 9, 28.50),  -- Crop week 12 (RID week 47)
('นครราชสีมา', 'นครราชสีมา', 39, 2025, 9, 28.50)   -- Crop week 13 (RID week 48)
ON CONFLICT (aos_station, province, calendar_week, calendar_year) DO NOTHING;

-- Also add the land preparation week (calendar week 26)
INSERT INTO ros.eto_weekly (aos_station, province, calendar_week, calendar_year, month, eto_value) VALUES
('นครราชสีมา', 'นครราชสีมา', 26, 2025, 6, 43.36)  -- Land prep week (one week before planting)
ON CONFLICT (aos_station, province, calendar_week, calendar_year) DO NOTHING;