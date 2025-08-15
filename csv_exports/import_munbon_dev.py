#!/usr/bin/env python3

import csv
import psycopg2
import json
import os
from datetime import datetime

# EC2 Database connection
EC2_CONFIG = {
    'host': '43.209.22.250',
    'port': 5432,
    'user': 'postgres',
    'password': 'P@ssw0rd123!',
    'database': 'munbon_dev'
}

def create_schemas_and_tables(cur):
    """Create schemas and tables if they don't exist"""
    
    # Create schemas
    cur.execute("CREATE SCHEMA IF NOT EXISTS gis")
    cur.execute("CREATE SCHEMA IF NOT EXISTS ros")
    
    # Create GIS tables
    gis_tables = """
    -- agricultural_plots
    CREATE TABLE IF NOT EXISTS gis.agricultural_plots (
        id SERIAL PRIMARY KEY,
        plot_id VARCHAR(255),
        area_hectares NUMERIC,
        crop_type VARCHAR(100),
        soil_type VARCHAR(100),
        irrigation_zone_id INTEGER,
        farmer_id VARCHAR(100),
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
        geom GEOMETRY(Polygon, 4326)
    );

    -- canal_network
    CREATE TABLE IF NOT EXISTS gis.canal_network (
        id SERIAL PRIMARY KEY,
        canal_id VARCHAR(255),
        canal_name VARCHAR(255),
        canal_type VARCHAR(100),
        length_km NUMERIC,
        capacity_cms NUMERIC,
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
        geom GEOMETRY(LineString, 4326)
    );

    -- control_structures
    CREATE TABLE IF NOT EXISTS gis.control_structures (
        id SERIAL PRIMARY KEY,
        structure_id VARCHAR(255),
        structure_type VARCHAR(100),
        structure_name VARCHAR(255),
        canal_id VARCHAR(255),
        capacity_cms NUMERIC,
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
        geom GEOMETRY(Point, 4326)
    );

    -- irrigation_zones
    CREATE TABLE IF NOT EXISTS gis.irrigation_zones (
        id SERIAL PRIMARY KEY,
        zone_id VARCHAR(50),
        zone_name VARCHAR(255),
        area_hectares NUMERIC,
        canal_id VARCHAR(255),
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
        geom GEOMETRY(MultiPolygon, 4326)
    );

    -- parcels
    CREATE TABLE IF NOT EXISTS gis.parcels (
        id SERIAL PRIMARY KEY,
        parcel_id VARCHAR(255),
        owner_name VARCHAR(255),
        area_sqm NUMERIC,
        land_use VARCHAR(100),
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
        geom GEOMETRY(Polygon, 4326)
    );

    -- ros_water_demands
    CREATE TABLE IF NOT EXISTS gis.ros_water_demands (
        id SERIAL PRIMARY KEY,
        zone_id VARCHAR(50),
        date DATE,
        water_demand_mcm NUMERIC,
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
    );

    -- sensor_locations
    CREATE TABLE IF NOT EXISTS gis.sensor_locations (
        id SERIAL PRIMARY KEY,
        sensor_id VARCHAR(255),
        sensor_type VARCHAR(100),
        installation_date DATE,
        status VARCHAR(50),
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
        geom GEOMETRY(Point, 4326)
    );

    -- shape_file_uploads
    CREATE TABLE IF NOT EXISTS gis.shape_file_uploads (
        id SERIAL PRIMARY KEY,
        file_name VARCHAR(255),
        file_type VARCHAR(50),
        upload_date TIMESTAMPTZ,
        processed BOOLEAN DEFAULT false,
        metadata JSONB
    );

    -- weather_stations
    CREATE TABLE IF NOT EXISTS gis.weather_stations (
        id SERIAL PRIMARY KEY,
        station_id VARCHAR(255),
        station_name VARCHAR(255),
        elevation_m NUMERIC,
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
        geom GEOMETRY(Point, 4326)
    );
    """
    
    # Create ROS tables
    ros_tables = """
    -- area_info
    CREATE TABLE IF NOT EXISTS ros.area_info (
        id SERIAL PRIMARY KEY,
        zone_id VARCHAR(50),
        zone_name VARCHAR(255),
        area_hectares NUMERIC,
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
    );

    -- crop_calendar
    CREATE TABLE IF NOT EXISTS ros.crop_calendar (
        id SERIAL PRIMARY KEY,
        crop_type VARCHAR(100),
        planting_date DATE,
        harvest_date DATE,
        zone_id VARCHAR(50),
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
    );

    -- effective_rainfall_monthly
    CREATE TABLE IF NOT EXISTS ros.effective_rainfall_monthly (
        id SERIAL PRIMARY KEY,
        month INTEGER,
        year INTEGER,
        rainfall_mm NUMERIC,
        effective_rainfall_mm NUMERIC,
        zone_id VARCHAR(50),
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
    );

    -- eto_monthly
    CREATE TABLE IF NOT EXISTS ros.eto_monthly (
        id SERIAL PRIMARY KEY,
        month INTEGER,
        year INTEGER,
        eto_mm NUMERIC,
        zone_id VARCHAR(50),
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
    );

    -- kc_weekly
    CREATE TABLE IF NOT EXISTS ros.kc_weekly (
        id SERIAL PRIMARY KEY,
        crop_type VARCHAR(100),
        week_number INTEGER,
        kc_value NUMERIC,
        growth_stage VARCHAR(100),
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
    );

    -- rainfall_data
    CREATE TABLE IF NOT EXISTS ros.rainfall_data (
        id SERIAL PRIMARY KEY,
        date DATE,
        rainfall_mm NUMERIC,
        station_id VARCHAR(255),
        zone_id VARCHAR(50),
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
    );

    -- water_demand_calculations
    CREATE TABLE IF NOT EXISTS ros.water_demand_calculations (
        id SERIAL PRIMARY KEY,
        date DATE,
        zone_id VARCHAR(50),
        crop_type VARCHAR(100),
        area_hectares NUMERIC,
        eto_mm NUMERIC,
        kc_value NUMERIC,
        effective_rainfall_mm NUMERIC,
        irrigation_requirement_mm NUMERIC,
        water_demand_mcm NUMERIC,
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
    );

    -- water_level_data
    CREATE TABLE IF NOT EXISTS ros.water_level_data (
        id SERIAL PRIMARY KEY,
        date DATE,
        time TIME,
        water_level_m NUMERIC,
        canal_id VARCHAR(255),
        sensor_id VARCHAR(255),
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
    );
    """
    
    # Execute table creation
    for statement in gis_tables.split(';'):
        if statement.strip():
            cur.execute(statement)
    
    for statement in ros_tables.split(';'):
        if statement.strip():
            cur.execute(statement)

def import_csv_file(cur, schema, table, file_path):
    """Import a CSV file into a table, handling geometry columns properly"""
    
    if not os.path.exists(file_path):
        print(f"  File not found: {file_path}")
        return 0
    
    # Get column info
    cur.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_schema = %s AND table_name = %s 
        ORDER BY ordinal_position
    """, (schema, table))
    
    columns = [(col[0], col[1]) for col in cur.fetchall()]
    
    # Read CSV and import
    with open(file_path, 'r') as f:
        reader = csv.DictReader(f)
        count = 0
        
        for row in reader:
            # Build column list and values based on CSV headers
            csv_columns = list(row.keys())
            insert_columns = []
            insert_values = []
            
            for col in csv_columns:
                if col in [c[0] for c in columns]:
                    insert_columns.append(col)
                    
                    # Handle special cases
                    if col == 'geom' and row[col]:
                        # Convert WKT to geometry
                        insert_values.append(f"ST_GeomFromText('{row[col]}', 4326)")
                    elif row[col] == '':
                        insert_values.append('NULL')
                    else:
                        insert_values.append(f"'{row[col]}'")
            
            if insert_columns:
                # Build and execute insert
                columns_str = ', '.join(insert_columns)
                values_str = ', '.join(insert_values)
                
                # Handle geometry columns specially
                values_str = values_str.replace("'ST_GeomFromText", "ST_GeomFromText").replace("', 4326)'", "', 4326)")
                values_str = values_str.replace("'NULL'", "NULL")
                
                query = f"INSERT INTO {schema}.{table} ({columns_str}) VALUES ({values_str})"
                cur.execute(query)
                count += 1
        
        return count

def import_munbon_dev_data():
    conn = psycopg2.connect(**EC2_CONFIG)
    cur = conn.cursor()
    
    try:
        print("Creating schemas and tables...")
        create_schemas_and_tables(cur)
        conn.commit()
        
        # Import GIS data
        print("\nImporting GIS schema tables...")
        gis_tables = [
            'agricultural_plots', 'canal_network', 'control_structures',
            'irrigation_zones', 'parcels', 'ros_water_demands',
            'sensor_locations', 'shape_file_uploads', 'weather_stations'
        ]
        
        for table in gis_tables:
            print(f"  Importing gis.{table}...")
            cur.execute(f"TRUNCATE TABLE gis.{table} RESTART IDENTITY CASCADE")
            count = import_csv_file(cur, 'gis', table, f'gis_data/{table}.csv')
            print(f"    Imported {count} rows")
            conn.commit()
        
        # Import ROS data
        print("\nImporting ROS schema tables...")
        ros_tables = [
            'area_info', 'crop_calendar', 'effective_rainfall_monthly',
            'eto_monthly', 'kc_weekly', 'rainfall_data',
            'water_demand_calculations', 'water_level_data'
        ]
        
        for table in ros_tables:
            print(f"  Importing ros.{table}...")
            cur.execute(f"TRUNCATE TABLE ros.{table} RESTART IDENTITY CASCADE")
            count = import_csv_file(cur, 'ros', table, f'ros_data/{table}.csv')
            print(f"    Imported {count} rows")
            conn.commit()
        
        # Verify imports
        print("\n=== Verification ===")
        
        print("\nGIS schema:")
        for table in gis_tables:
            cur.execute(f"SELECT COUNT(*) FROM gis.{table}")
            count = cur.fetchone()[0]
            print(f"  gis.{table}: {count} rows")
        
        print("\nROS schema:")
        for table in ros_tables:
            cur.execute(f"SELECT COUNT(*) FROM ros.{table}")
            count = cur.fetchone()[0]
            print(f"  ros.{table}: {count} rows")
            
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    import_munbon_dev_data()