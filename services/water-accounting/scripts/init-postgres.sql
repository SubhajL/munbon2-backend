-- Initialize PostgreSQL database for Water Accounting Service

-- Create database if not exists (run as superuser)
-- CREATE DATABASE munbon_water_accounting;

-- Connect to the database
\c munbon_water_accounting;

-- Create user if not exists (run as superuser)
-- CREATE USER water_accounting_user WITH PASSWORD 'water_accounting_pass';

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE munbon_water_accounting TO water_accounting_user;

-- Create schema
CREATE SCHEMA IF NOT EXISTS water_accounting;
GRANT ALL ON SCHEMA water_accounting TO water_accounting_user;

-- Set search path
ALTER DATABASE munbon_water_accounting SET search_path TO water_accounting, public;

-- Create PostGIS extension for spatial data (if needed)
CREATE EXTENSION IF NOT EXISTS postgis;

-- Create UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create helper functions

-- Function to generate section IDs
CREATE OR REPLACE FUNCTION generate_section_id(p_zone_id TEXT, p_section_number INTEGER)
RETURNS TEXT AS $$
BEGIN
    RETURN FORMAT('SEC-%s-%03s', p_zone_id, p_section_number::TEXT);
END;
$$ LANGUAGE plpgsql;

-- Function to generate delivery IDs
CREATE OR REPLACE FUNCTION generate_delivery_id(p_section_id TEXT, p_date DATE)
RETURNS TEXT AS $$
BEGIN
    RETURN FORMAT('DEL-%s-%s-%03s', 
        TO_CHAR(p_date, 'YYYYMMDD'),
        p_section_id,
        COALESCE(
            (SELECT COUNT(*) + 1 
             FROM water_deliveries 
             WHERE section_id = p_section_id 
               AND DATE(scheduled_start) = p_date),
            1
        )
    );
END;
$$ LANGUAGE plpgsql;

-- Function to calculate deficit percentage
CREATE OR REPLACE FUNCTION calculate_deficit_percentage(
    p_demand DOUBLE PRECISION,
    p_delivered DOUBLE PRECISION
) RETURNS DOUBLE PRECISION AS $$
BEGIN
    IF p_demand <= 0 THEN
        RETURN 0;
    END IF;
    RETURN ((p_demand - p_delivered) / p_demand) * 100;
END;
$$ LANGUAGE plpgsql;

-- Function to determine stress level based on deficit
CREATE OR REPLACE FUNCTION determine_stress_level(
    p_deficit_percentage DOUBLE PRECISION
) RETURNS TEXT AS $$
BEGIN
    IF p_deficit_percentage <= 0 THEN
        RETURN 'none';
    ELSIF p_deficit_percentage <= 10 THEN
        RETURN 'mild';
    ELSIF p_deficit_percentage <= 20 THEN
        RETURN 'moderate';
    ELSIF p_deficit_percentage <= 30 THEN
        RETURN 'severe';
    ELSE
        RETURN 'critical';
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Function to calculate priority score for deficit recovery
CREATE OR REPLACE FUNCTION calculate_priority_score(
    p_deficit_amount DOUBLE PRECISION,
    p_deficit_weeks INTEGER,
    p_stress_level TEXT,
    p_location_factor DOUBLE PRECISION DEFAULT 1.0
) RETURNS DOUBLE PRECISION AS $$
DECLARE
    v_amount_score DOUBLE PRECISION;
    v_age_score DOUBLE PRECISION;
    v_stress_score DOUBLE PRECISION;
BEGIN
    -- Base score from deficit amount (0-40 points)
    v_amount_score := LEAST(40, (p_deficit_amount / 10000) * 40);
    
    -- Age factor (0-30 points)
    v_age_score := LEAST(30, p_deficit_weeks * 7.5);
    
    -- Stress factor (0-30 points)
    v_stress_score := CASE p_stress_level
        WHEN 'critical' THEN 30
        WHEN 'severe' THEN 25
        WHEN 'moderate' THEN 20
        WHEN 'mild' THEN 10
        ELSE 0
    END;
    
    -- Apply location factor and return total
    RETURN (v_amount_score + v_age_score + v_stress_score) * p_location_factor;
END;
$$ LANGUAGE plpgsql;

-- Create triggers for updated_at timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply triggers to tables with updated_at columns
-- (These will be created after Alembic migrations run)

-- Create views for common queries

-- View for current section status
CREATE OR REPLACE VIEW v_section_current_status AS
SELECT 
    s.id,
    s.name,
    s.zone_id,
    s.area_hectares,
    s.primary_crop,
    s.crop_stage,
    sm.delivery_efficiency,
    sm.application_efficiency,
    sm.overall_efficiency,
    sm.current_deficit_m3,
    sm.deficit_weeks,
    sm.last_updated
FROM sections s
LEFT JOIN LATERAL (
    SELECT *
    FROM section_metrics
    WHERE section_id = s.id
    ORDER BY last_updated DESC
    LIMIT 1
) sm ON true
WHERE s.active = true;

-- View for weekly deficit summary
CREATE OR REPLACE VIEW v_weekly_deficit_summary AS
SELECT 
    week_number,
    year,
    COUNT(DISTINCT section_id) as sections_in_deficit,
    SUM(delivery_deficit_m3) as total_deficit_m3,
    AVG(deficit_percentage) as avg_deficit_percentage,
    COUNT(CASE WHEN stress_level = 'severe' OR stress_level = 'critical' THEN 1 END) as severe_stress_count
FROM deficit_records
GROUP BY week_number, year
ORDER BY year DESC, week_number DESC;

-- Grant permissions on functions and views
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA water_accounting TO water_accounting_user;
GRANT SELECT ON ALL TABLES IN SCHEMA water_accounting TO water_accounting_user;