#!/usr/bin/env python3
"""
Import RID-MS water requirements and manual water level data to EC2 database.
Processes geopackage files from data_ridplan and data_water_level folders.
"""

import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor
import geopandas as gpd
from datetime import datetime
import logging
import sys
from shapely import wkt
from shapely.geometry import Point
import pandas as pd
import numpy as np

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# EC2 Database connection parameters
# Connect to Docker container on EC2
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,  # Postgres port on EC2
    'database': 'munbon_dev',
    'user': 'postgres',
    'password': os.getenv('POSTGRES_PASSWORD', 'YourSecurePasswordHere123!')  # From EC2 config
}

def connect_to_db():
    """Create database connection."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        logger.info("Successfully connected to EC2 database")
        return conn
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        raise

def process_ridplan_data(gpkg_path):
    """Process RID-MS water requirements data from geopackage."""
    logger.info(f"Processing RID-MS data from: {gpkg_path}")
    
    try:
        # Read geopackage
        gdf = gpd.read_file(gpkg_path)
        logger.info(f"Loaded {len(gdf)} records from ridplan geopackage")
        
        # Convert to WGS84 if needed
        if gdf.crs and gdf.crs.to_epsg() != 4326:
            gdf = gdf.to_crs(epsg=4326)
            logger.info("Converted CRS to WGS84")
        
        # Process each record
        parcels_data = []
        for idx, row in gdf.iterrows():
            parcel_data = {
                'parcel_seq': row.get('PARCEL_SEQ'),
                'zone_area': row.get('zone_area'),
                'area_rai': float(row.get('area_rai', 0)),
                'batch_date': int(row.get('batch_date_int', 0)),
                'start_date': int(row.get('start_int', 0)),
                'crop_cycle': int(row.get('crop_cycle', 0)),
                'wpet': float(row.get('wpet', 0)),
                'wprod': float(row.get('wprod', 0)),
                'age': int(row.get('age', 0)),
                'plant_id': row.get('plant_id'),
                'stage_age': int(row.get('stage_age', 0)),
                'yield_at_mc_kgpr': float(row.get('yield_at_mc_kgpr', 0)),
                'season_rain_m3_per_rai': float(row.get('season_rain_m3_per_rai', 0)),
                'season_irri_m3_per_rai': float(row.get('season_irri_m3_per_rai', 0)),
                'season_water_input_m3_per_rai': float(row.get('season_water_input_m3_per_rai', 0)),
                'auto_note': row.get('auto_note'),
                'geometry': row.geometry.wkt if row.geometry else None
            }
            
            # Parse auto_note if it's a JSON string
            if parcel_data['auto_note'] and isinstance(parcel_data['auto_note'], str):
                try:
                    parcel_data['watering_plan'] = json.loads(parcel_data['auto_note'])
                except:
                    parcel_data['watering_plan'] = None
            
            parcels_data.append(parcel_data)
        
        return parcels_data
        
    except Exception as e:
        logger.error(f"Error processing RID-MS data: {e}")
        raise

def process_water_level_data(gpkg_path):
    """Process manual water level data from geopackage."""
    logger.info(f"Processing water level data from: {gpkg_path}")
    
    try:
        # Read geopackage
        gdf = gpd.read_file(gpkg_path)
        logger.info(f"Loaded {len(gdf)} water level records")
        
        # Convert to WGS84 if needed
        if gdf.crs and gdf.crs.to_epsg() != 4326:
            gdf = gdf.to_crs(epsg=4326)
            logger.info("Converted CRS to WGS84")
        
        # Process each record
        water_level_data = []
        for idx, row in gdf.iterrows():
            # Extract centroid coordinates
            centroid = row.geometry.centroid if row.geometry else None
            
            record = {
                'crop_id': row.get('crop_id'),
                'project_name': row.get('project_name'),
                'lat': float(row.get('lat_y', 0)),
                'lon': float(row.get('lon_x', 0)),
                'act_date': row.get('act_date'),
                'water_level_mm': float(row.get('water_level_mm', 0)) if row.get('water_level_mm') else 0,
                'coordinates': Point(centroid.x, centroid.y).wkt if centroid else None
            }
            
            water_level_data.append(record)
        
        return water_level_data
        
    except Exception as e:
        logger.error(f"Error processing water level data: {e}")
        raise

def import_ridplan_to_db(conn, parcels_data):
    """Import RID-MS parcels data to database."""
    logger.info("Importing RID-MS data to database")
    
    cursor = conn.cursor()
    
    try:
        # Insert into gis.parcels table as JSONB
        insert_count = 0
        for parcel in parcels_data:
            # Create JSONB data
            parcel_json = {
                'type': 'rid_ms_parcel',
                'source': 'excel_rice_20250810_merge',
                'import_date': datetime.now().isoformat(),
                'parcel_data': parcel
            }
            
            cursor.execute("""
                INSERT INTO gis.parcels (data)
                VALUES (%s)
            """, (json.dumps(parcel_json),))
            
            insert_count += 1
        
        conn.commit()
        logger.info(f"Successfully imported {insert_count} RID-MS parcels")
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error importing RID-MS data: {e}")
        raise
    finally:
        cursor.close()

def import_water_levels_to_db(conn, water_level_data):
    """Import manual water level readings to database."""
    logger.info("Importing water level data to database")
    
    cursor = conn.cursor()
    
    try:
        insert_count = 0
        for record in water_level_data:
            # Convert water level from mm to meters
            water_level_m = record['water_level_mm'] / 1000.0
            
            # Parse date
            reading_date = datetime.strptime(record['act_date'], '%Y-%m-%d').date()
            
            # Create WKT point from coordinates
            point_wkt = f"POINT({record['lon']} {record['lat']})"
            
            cursor.execute("""
                INSERT INTO ros_gis.manual_water_level_readings 
                (location_id, section_id, plot_id, water_level_m, reading_date,
                 volunteer_name, geopackage_source, coordinates, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, ST_GeomFromText(%s, 4326), %s)
            """, (
                record['crop_id'],
                'MB-001',  # Default section ID - update as needed
                record['project_name'],
                water_level_m,
                reading_date,
                'RID-MS Import',
                'data_water_level.gpkg',
                point_wkt,
                f"Original water level: {record['water_level_mm']}mm"
            ))
            
            insert_count += 1
        
        conn.commit()
        logger.info(f"Successfully imported {insert_count} water level readings")
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error importing water level data: {e}")
        raise
    finally:
        cursor.close()

def main():
    """Main function to process and import data."""
    logger.info("Starting data import process")
    
    # File paths
    ridplan_gpkg = "data_ridplan/excel_rice_20250810_merge/excel_rice_20250810_merge.gpkg"
    water_level_gpkg = "data_water_level/data_water_level.gpkg"
    
    # Check if files exist
    if not os.path.exists(ridplan_gpkg):
        logger.error(f"RID-MS file not found: {ridplan_gpkg}")
        return
    
    if not os.path.exists(water_level_gpkg):
        logger.error(f"Water level file not found: {water_level_gpkg}")
        return
    
    # Connect to database
    conn = connect_to_db()
    
    try:
        # Process and import RID-MS data
        parcels_data = process_ridplan_data(ridplan_gpkg)
        import_ridplan_to_db(conn, parcels_data)
        
        # Process and import water level data
        water_level_data = process_water_level_data(water_level_gpkg)
        import_water_levels_to_db(conn, water_level_data)
        
        logger.info("Data import completed successfully")
        
    except Exception as e:
        logger.error(f"Import process failed: {e}")
        raise
    finally:
        conn.close()
        logger.info("Database connection closed")

if __name__ == "__main__":
    main()