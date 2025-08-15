-- Update effective rainfall values to match Excel exactly
-- Excel shows daily values, we store monthly values

-- Calculate monthly from Excel daily values (daily * days in month)
UPDATE ros.effective_rainfall_monthly
SET effective_rainfall_mm = CASE month
    WHEN 1 THEN 0.148387 * 31  -- 4.60 mm
    WHEN 2 THEN 0.732143 * 28  -- 20.50 mm (non-leap year)
    WHEN 3 THEN 1.341935 * 31  -- 41.60 mm
    WHEN 4 THEN 2.193333 * 30  -- 65.80 mm
    WHEN 5 THEN 4.906452 * 31  -- 152.10 mm
    WHEN 6 THEN 3.483333 * 30  -- 104.50 mm
    WHEN 7 THEN 3.951613 * 31  -- 122.50 mm
    WHEN 8 THEN 4.129032 * 31  -- 128.00 mm
    WHEN 9 THEN 7.773333 * 30  -- 233.20 mm
    WHEN 10 THEN 4.906452 * 31 -- 152.10 mm
    WHEN 11 THEN 1.033333 * 30 -- 31.00 mm
    WHEN 12 THEN 0.116129 * 31 -- 3.60 mm
    END,
    updated_at = NOW()
WHERE aos_station = 'นครราชสีมา'
  AND province = 'นครราชสีมา' 
  AND crop_type = 'rice';

-- Show updated values
SELECT 
  month,
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
  END as month_abbr,
  effective_rainfall_mm as monthly_mm,
  ROUND((effective_rainfall_mm / CASE 
    WHEN month IN (1,3,5,7,8,10,12) THEN 31
    WHEN month IN (4,6,9,11) THEN 30
    WHEN month = 2 THEN 28
  END)::numeric, 6) as daily_mm,
  CASE 
    WHEN month IN (1,3,5,7,8,10,12) THEN 31
    WHEN month IN (4,6,9,11) THEN 30
    WHEN month = 2 THEN 28
  END as days_in_month
FROM ros.effective_rainfall_monthly
WHERE aos_station = 'นครราชสีมา'
  AND crop_type = 'rice'
ORDER BY month;