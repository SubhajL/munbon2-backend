#!/usr/bin/env python3

import csv
import psycopg2
import psycopg2.extras
import os
from io import StringIO

# EC2 Database connection
EC2_CONFIG = {
    'host': os.environ.get('EC2_HOST', '43.208.201.191'),
    'port': 5432,
    'user': 'postgres',
    'password': 'P@ssw0rd123!',
    'database': 'munbon_dev'
}

def import_with_copy(cur, schema, table, csv_path):
    """Use COPY for faster imports"""
    
    if not os.path.exists(csv_path):
        print(f"    File not found: {csv_path}")
        return 0
    
    # For tables with geometry, we need special handling
    geometry_tables = ['agricultural_plots', 'canal_network', 'control_structures', 
                      'irrigation_zones', 'parcels', 'sensor_locations', 'weather_stations']
    
    if table in geometry_tables:
        # Create temp table without geometry
        cur.execute(f"""
            CREATE TEMP TABLE temp_{table} AS 
            SELECT * FROM {schema}.{table} 
            WHERE false
        """)
        
        # Remove geometry column from temp table
        cur.execute(f"ALTER TABLE temp_{table} DROP COLUMN IF EXISTS geom")
        
        # Copy to temp table
        with open(csv_path, 'r') as f:
            # Skip header and check if file has data
            header = f.readline()
            if not f.readline():  # Check if there's at least one data line
                print(f"    No data in {csv_path}")
                return 0
            f.seek(0)  # Reset to beginning
            
            # Get columns from header (excluding geom)
            columns = [col.strip() for col in header.split(',') if col.strip() != 'geom']
            columns_str = ','.join(columns)
            
            # Use COPY
            cur.copy_expert(f"COPY temp_{table} ({columns_str}) FROM STDIN WITH CSV HEADER", f)
        
        # Count rows
        cur.execute(f"SELECT COUNT(*) FROM temp_{table}")
        count = cur.fetchone()[0]
        
        # Insert from temp to real table (without geometry for now)
        if count > 0:
            cur.execute(f"""
                INSERT INTO {schema}.{table} ({columns_str})
                SELECT {columns_str} FROM temp_{table}
            """)
        
        return count
    else:
        # For non-geometry tables, use direct COPY
        with open(csv_path, 'r') as f:
            cur.copy_expert(f"COPY {schema}.{table} FROM STDIN WITH CSV HEADER", f)
        
        # Get count
        cur.execute(f"SELECT COUNT(*) FROM {schema}.{table}")
        return cur.fetchone()[0]

def import_munbon_dev_data():
    conn = psycopg2.connect(**EC2_CONFIG)
    cur = conn.cursor()
    
    try:
        # Create schemas
        print("Creating schemas...")
        cur.execute("CREATE SCHEMA IF NOT EXISTS gis")
        cur.execute("CREATE SCHEMA IF NOT EXISTS ros")
        
        # First, let's just import non-geometry tables and smaller tables
        print("\nImporting smaller tables first...")
        
        # GIS tables without large geometries
        small_gis_tables = [
            ('ros_water_demands', 'gis_data/ros_water_demands.csv'),
            ('shape_file_uploads', 'gis_data/shape_file_uploads.csv'),
        ]
        
        for table, path in small_gis_tables:
            print(f"  Importing gis.{table}...")
            
            # Create table if needed
            if table == 'ros_water_demands':
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS gis.ros_water_demands (
                        id SERIAL PRIMARY KEY,
                        zone_id VARCHAR(50),
                        date DATE,
                        water_demand_mcm NUMERIC,
                        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                    )
                """)
            elif table == 'shape_file_uploads':
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS gis.shape_file_uploads (
                        id SERIAL PRIMARY KEY,
                        file_name VARCHAR(255),
                        file_type VARCHAR(50),
                        upload_date TIMESTAMPTZ,
                        processed BOOLEAN DEFAULT false,
                        metadata JSONB
                    )
                """)
            
            cur.execute(f"TRUNCATE TABLE gis.{table} RESTART IDENTITY CASCADE")
            
            if os.path.exists(path):
                with open(path, 'r') as f:
                    cur.copy_expert(f"COPY gis.{table} FROM STDIN WITH CSV HEADER", f)
                
                cur.execute(f"SELECT COUNT(*) FROM gis.{table}")
                count = cur.fetchone()[0]
                print(f"    Imported {count} rows")
            
            conn.commit()
        
        # Import all ROS tables
        print("\nImporting ROS schema tables...")
        
        ros_table_defs = {
            'area_info': """
                CREATE TABLE IF NOT EXISTS ros.area_info (
                    id SERIAL PRIMARY KEY,
                    zone_id VARCHAR(50),
                    zone_name VARCHAR(255),
                    area_hectares NUMERIC,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
            """,
            'crop_calendar': """
                CREATE TABLE IF NOT EXISTS ros.crop_calendar (
                    id SERIAL PRIMARY KEY,
                    crop_type VARCHAR(100),
                    planting_date DATE,
                    harvest_date DATE,
                    zone_id VARCHAR(50),
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
            """,
            'effective_rainfall_monthly': """
                CREATE TABLE IF NOT EXISTS ros.effective_rainfall_monthly (
                    id SERIAL PRIMARY KEY,
                    month INTEGER,
                    year INTEGER,
                    rainfall_mm NUMERIC,
                    effective_rainfall_mm NUMERIC,
                    zone_id VARCHAR(50),
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
            """,
            'eto_monthly': """
                CREATE TABLE IF NOT EXISTS ros.eto_monthly (
                    id SERIAL PRIMARY KEY,
                    month INTEGER,
                    year INTEGER,
                    eto_mm NUMERIC,
                    zone_id VARCHAR(50),
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
            """,
            'kc_weekly': """
                CREATE TABLE IF NOT EXISTS ros.kc_weekly (
                    id SERIAL PRIMARY KEY,
                    crop_type VARCHAR(100),
                    week_number INTEGER,
                    kc_value NUMERIC,
                    growth_stage VARCHAR(100),
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
            """,
            'rainfall_data': """
                CREATE TABLE IF NOT EXISTS ros.rainfall_data (
                    id SERIAL PRIMARY KEY,
                    date DATE,
                    rainfall_mm NUMERIC,
                    station_id VARCHAR(255),
                    zone_id VARCHAR(50),
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
            """,
            'water_demand_calculations': """
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
                )
            """,
            'water_level_data': """
                CREATE TABLE IF NOT EXISTS ros.water_level_data (
                    id SERIAL PRIMARY KEY,
                    date DATE,
                    time TIME,
                    water_level_m NUMERIC,
                    canal_id VARCHAR(255),
                    sensor_id VARCHAR(255),
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
            """
        }
        
        for table, create_sql in ros_table_defs.items():
            print(f"  Importing ros.{table}...")
            cur.execute(create_sql)
            cur.execute(f"TRUNCATE TABLE ros.{table} RESTART IDENTITY CASCADE")
            
            csv_path = f'ros_data/{table}.csv'
            if os.path.exists(csv_path):
                with open(csv_path, 'r') as f:
                    # Skip files with only header
                    first_line = f.readline()
                    if f.readline():  # Has data
                        f.seek(0)
                        cur.copy_expert(f"COPY ros.{table} FROM STDIN WITH CSV HEADER", f)
                
                cur.execute(f"SELECT COUNT(*) FROM ros.{table}")
                count = cur.fetchone()[0]
                print(f"    Imported {count} rows")
            
            conn.commit()
        
        # Final verification
        print("\n=== Verification ===")
        
        print("\nGIS schema:")
        cur.execute("""
            SELECT table_name, 
                   (SELECT COUNT(*) FROM gis.ros_water_demands WHERE table_name = 'ros_water_demands') as count
            FROM information_schema.tables 
            WHERE table_schema = 'gis' AND table_name IN ('ros_water_demands', 'shape_file_uploads')
            ORDER BY table_name
        """)
        
        cur.execute("SELECT COUNT(*) FROM gis.ros_water_demands")
        print(f"  gis.ros_water_demands: {cur.fetchone()[0]} rows")
        
        cur.execute("SELECT COUNT(*) FROM gis.shape_file_uploads") 
        print(f"  gis.shape_file_uploads: {cur.fetchone()[0]} rows")
        
        print("\nROS schema:")
        for table in ros_table_defs.keys():
            cur.execute(f"SELECT COUNT(*) FROM ros.{table}")
            print(f"  ros.{table}: {cur.fetchone()[0]} rows")
        
        print("\nNote: Large GIS tables with geometry (agricultural_plots, etc.) were skipped for now")
        print("      due to size. They can be imported separately if needed.")
            
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    import_munbon_dev_data()