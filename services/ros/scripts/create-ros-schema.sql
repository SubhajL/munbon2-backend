-- Create ROS schema if it doesn't exist
CREATE SCHEMA IF NOT EXISTS ros;

-- Set search path to include ros schema
SET search_path TO ros, public;

-- Grant permissions
GRANT ALL ON SCHEMA ros TO postgres;
GRANT USAGE ON SCHEMA ros TO munbon_app;
GRANT SELECT ON ALL TABLES IN SCHEMA ros TO munbon_reader;

-- Create update_updated_at_column function if it doesn't exist
CREATE OR REPLACE FUNCTION ros.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Now run the schema update to create tables in ros schema