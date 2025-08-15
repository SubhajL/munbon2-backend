#!/usr/bin/env python3
"""
Import parcels from GeoPackage to ros.plots table

This script:
1. Extracts parcels from merge3Amp_32648_edit20230721.gpkg
2. Imports them into the ros.plots table
3. Assigns them to appropriate sections/zones based on sub_member field
"""

import geopandas as gpd
import psycopg2
from psycopg2.extras import RealDictCursor
from shapely.geometry import shape
from shapely.wkt import dumps as wkt_dumps
import json
import sys
from datetime import datetime

# Database connection parameters
DB_CONFIG = {
    'host': 'localhost',
    'port': 5434,
    'database': 'munbon_dev',
    'user': 'postgres',
    'password': 'postgres'
}

def connect_to_db():
    """Connect to the database"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        print(f"Error connecting to database: {e}")
        sys.exit(1)

def check_ros_schema(conn):
    """Check if ros schema and plots table exist"""
    with conn.cursor() as cursor:
        # Check if ros schema exists
        cursor.execute("""
            SELECT schema_name 
            FROM information_schema.schemata 
            WHERE schema_name = 'ros'
        """)
        if not cursor.fetchone():
            print("Creating ros schema...")
            cursor.execute("CREATE SCHEMA ros")
            conn.commit()
        
        # Check if plots table exists
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'ros' AND table_name = 'plots'
        """)
        if not cursor.fetchone():
            print("Creating ros.plots table...")
            cursor.execute("""
                -- Create plot information table
                CREATE TABLE IF NOT EXISTS ros.plots (
                    id SERIAL PRIMARY KEY,
                    plot_id VARCHAR(50) UNIQUE NOT NULL,
                    plot_code VARCHAR(50),
                    area_rai DECIMAL(10,2) NOT NULL,
                    geometry GEOMETRY(Polygon, 32648),
                    parent_section_id VARCHAR(50),
                    parent_zone_id VARCHAR(50),
                    aos_station VARCHAR(100) DEFAULT 'นครราชสีมา',
                    province VARCHAR(100) DEFAULT 'นครราชสีมา',
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                );
                
                -- Create indexes
                CREATE INDEX IF NOT EXISTS idx_plots_geometry ON ros.plots USING GIST(geometry);
                CREATE INDEX IF NOT EXISTS idx_plots_parent_section ON ros.plots(parent_section_id);
                CREATE INDEX IF NOT EXISTS idx_plots_parent_zone ON ros.plots(parent_zone_id);
            """)
            conn.commit()

def extract_parcels_from_geopackage(gpkg_path):
    """Extract parcels from GeoPackage"""
    print(f"Reading GeoPackage: {gpkg_path}")
    
    # Read the GeoPackage
    gdf = gpd.read_file(gpkg_path)
    
    print(f"Found {len(gdf)} parcels in GeoPackage")
    print(f"CRS: {gdf.crs}")
    print(f"Columns: {list(gdf.columns)}")
    
    # Check first few records
    print("\nFirst 3 records:")
    for idx, row in gdf.head(3).iterrows():
        print(f"  PARCEL_SEQ: {row.get('PARCEL_SEQ', 'N/A')}")
        print(f"  sub_member: {row.get('sub_member', 'N/A')}")
        print(f"  parcel_are: {row.get('parcel_are', 'N/A')} rai")
        print(f"  plant_id: {row.get('plant_id', 'N/A')}")
        print("  ---")
    
    return gdf

def determine_zone_and_section(sub_member):
    """Determine zone and section IDs based on sub_member value"""
    if pd.isna(sub_member):
        return 'zone_1', 'section_1'
    
    sub_member_int = int(sub_member)
    
    # Simple mapping: sub_member 1-3 -> zone_1, 4-6 -> zone_2, etc.
    zone_num = ((sub_member_int - 1) // 3) + 1
    section_num = ((sub_member_int - 1) // 10) + 1
    
    return f'zone_{zone_num}', f'section_{section_num}'

def import_parcels_to_ros(conn, gdf):
    """Import parcels into ros.plots table"""
    cursor = conn.cursor()
    
    # Clear existing data (optional - comment out if you want to append)
    print("Clearing existing data in ros.plots...")
    cursor.execute("TRUNCATE TABLE ros.plots RESTART IDENTITY CASCADE")
    conn.commit()
    
    success_count = 0
    error_count = 0
    
    print(f"\nImporting {len(gdf)} parcels...")
    
    for idx, row in gdf.iterrows():
        try:
            # Extract data
            parcel_seq = row.get('PARCEL_SEQ', f'P{idx}')
            plot_code = row.get('PARCEL_SEQ', f'P{idx}')
            area_rai = float(row.get('parcel_are', 0))
            sub_member = row.get('sub_member', 1)
            
            # Determine zone and section
            zone_id, section_id = determine_zone_and_section(sub_member)
            
            # Get geometry in WKT format (already in EPSG:32648)
            geom_wkt = row.geometry.wkt
            
            # Insert into database
            cursor.execute("""
                INSERT INTO ros.plots (
                    plot_id, plot_code, area_rai, geometry,
                    parent_section_id, parent_zone_id,
                    aos_station, province
                ) VALUES (
                    %s, %s, %s, ST_GeomFromText(%s, 32648),
                    %s, %s, %s, %s
                )
                ON CONFLICT (plot_id) DO UPDATE SET
                    plot_code = EXCLUDED.plot_code,
                    area_rai = EXCLUDED.area_rai,
                    geometry = EXCLUDED.geometry,
                    parent_section_id = EXCLUDED.parent_section_id,
                    parent_zone_id = EXCLUDED.parent_zone_id,
                    updated_at = NOW()
            """, (
                parcel_seq,
                plot_code,
                area_rai,
                geom_wkt,
                section_id,
                zone_id,
                'นครราชสีมา',
                'นครราชสีมา'
            ))
            
            success_count += 1
            
            # Progress indicator
            if (idx + 1) % 100 == 0:
                print(f"  Processed {idx + 1}/{len(gdf)} parcels...")
                conn.commit()
        
        except Exception as e:
            error_count += 1
            print(f"Error importing parcel {parcel_seq}: {e}")
            conn.rollback()
    
    # Final commit
    conn.commit()
    
    print(f"\nImport completed:")
    print(f"  Success: {success_count}")
    print(f"  Errors: {error_count}")
    
    # Verify import
    cursor.execute("SELECT COUNT(*) FROM ros.plots")
    total_count = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT parent_zone_id, COUNT(*) as count 
        FROM ros.plots 
        GROUP BY parent_zone_id 
        ORDER BY parent_zone_id
    """)
    zone_counts = cursor.fetchall()
    
    print(f"\nTotal parcels in database: {total_count}")
    print("Parcels by zone:")
    for zone_id, count in zone_counts:
        print(f"  {zone_id}: {count} parcels")
    
    cursor.close()

def main():
    """Main function"""
    # Path to GeoPackage
    gpkg_path = '/Users/subhajlimanond/dev/munbon2-backend/merge3Amp_32648_edit20230721.gpkg'
    
    # Connect to database
    print("Connecting to database...")
    conn = connect_to_db()
    
    try:
        # Check/create schema and table
        check_ros_schema(conn)
        
        # Extract parcels from GeoPackage
        gdf = extract_parcels_from_geopackage(gpkg_path)
        
        # Import parcels to database
        import_parcels_to_ros(conn, gdf)
        
        print("\nImport process completed successfully!")
        
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    # Import pandas here to avoid import error if not needed
    import pandas as pd
    main()