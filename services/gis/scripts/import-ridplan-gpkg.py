#!/usr/bin/env python3
import sqlite3
import psycopg2
import json
import sys
import uuid
from datetime import datetime

def import_ridplan_to_postgis(gpkg_path):
    """Import RID Plan GeoPackage to PostGIS"""
    
    # Connect to PostgreSQL
    pg_conn = psycopg2.connect(
        host="localhost",
        port=5434,
        database="munbon_dev",
        user="postgres",
        password="postgres"
    )
    pg_cursor = pg_conn.cursor()
    
    # Connect to GeoPackage
    gpkg_conn = sqlite3.connect(gpkg_path)
    gpkg_cursor = gpkg_conn.cursor()
    
    print(f"Processing GeoPackage: {gpkg_path}")
    
    # Get default zone ID
    pg_cursor.execute("""
        SELECT id FROM gis.irrigation_zones 
        WHERE zone_code = 'Z001' 
        LIMIT 1
    """)
    result = pg_cursor.fetchone()
    
    if result:
        default_zone_id = result[0]
    else:
        # Create default zone
        pg_cursor.execute("""
            INSERT INTO gis.irrigation_zones (id, zone_code, zone_name, zone_type, boundary)
            VALUES (%s, 'Z001', 'Zone 1', 'irrigation', 
                    ST_GeomFromText('POLYGON((102 14, 103 14, 103 15, 102 15, 102 14))', 4326))
            RETURNING id
        """, (str(uuid.uuid4()),))
        default_zone_id = pg_cursor.fetchone()[0]
        pg_conn.commit()
    
    print(f"Using default zone: {default_zone_id}")
    
    # Get total count
    gpkg_cursor.execute("SELECT COUNT(*) FROM ridplan_rice_20250702")
    total_count = gpkg_cursor.fetchone()[0]
    print(f"Total features to import: {total_count}")
    
    # Process in batches
    batch_size = 100
    processed = 0
    saved = 0
    errors = []
    
    upload_id = f"ridplan-import-{int(datetime.now().timestamp())}"
    
    for offset in range(0, total_count, batch_size):
        gpkg_cursor.execute(f"""
            SELECT 
                fid, PARCEL_SEQ, AMPHOE_T, TAM_NAM_T,
                lat, lon, area, parcel_area_rai,
                data_date_process, start_int, wpet, age,
                wprod, plant_id, yield_at_mc_kgpr,
                season_irri_m3_per_rai, auto_note
            FROM ridplan_rice_20250702
            LIMIT {batch_size} OFFSET {offset}
        """)
        
        rows = gpkg_cursor.fetchall()
        
        for row in rows:
            try:
                parcel_id = str(uuid.uuid4())
                plot_code = row[1] or f"RID-{row[0]}"
                area_hectares = row[6] / 10000  # Convert from sq meters
                
                # Create properties JSON
                properties = {
                    "uploadId": upload_id,
                    "ridAttributes": {
                        "parcelAreaRai": row[7],
                        "dataDateProcess": datetime.fromtimestamp(row[8]).isoformat() if row[8] else None,
                        "startInt": datetime.fromtimestamp(row[9]).isoformat() if row[9] else None,
                        "wpet": row[10],
                        "age": row[11],
                        "wprod": row[12],
                        "plantId": row[13],
                        "yieldAtMcKgpr": row[14],
                        "seasonIrrM3PerRai": row[15],
                        "autoNote": row[16]
                    },
                    "location": {
                        "amphoe": row[2],
                        "tambon": row[3],
                        "lat": row[4],
                        "lon": row[5]
                    },
                    "lastUpdated": datetime.now().isoformat()
                }
                
                # Insert into PostGIS
                # Create a small buffer around the point to make it a polygon
                # Using approximately 50 meters buffer (0.0005 degrees)
                pg_cursor.execute("""
                    INSERT INTO gis.agricultural_plots (
                        id, plot_code, farmer_id, zone_id, area_hectares,
                        boundary, current_crop_type, soil_type, properties
                    ) VALUES (
                        %s, %s, %s, %s, %s,
                        ST_Buffer(ST_GeomFromText('POINT(%s %s)', 4326)::geography, 50)::geometry,
                        %s, %s, %s::jsonb
                    )
                    ON CONFLICT (plot_code) DO UPDATE SET
                        area_hectares = EXCLUDED.area_hectares,
                        boundary = EXCLUDED.boundary,
                        properties = EXCLUDED.properties,
                        updated_at = NOW()
                """, (
                    parcel_id,
                    plot_code,
                    'unknown',  # farmer_id
                    default_zone_id,
                    area_hectares,
                    row[5], row[4],  # lon, lat
                    row[13] or 'rice',  # crop type
                    'unknown',  # soil type
                    json.dumps(properties)
                ))
                
                saved += 1
                
            except Exception as e:
                errors.append(f"Error processing FID {row[0]}: {str(e)}")
                if len(errors) <= 5:
                    print(f"Error: {errors[-1]}")
        
        pg_conn.commit()
        processed += len(rows)
        
        if processed % 1000 == 0:
            progress = (processed / total_count) * 100
            print(f"Progress: {processed}/{total_count} ({progress:.1f}%)")
    
    # Close connections
    gpkg_conn.close()
    pg_conn.close()
    
    # Summary
    print("\n=== Import Summary ===")
    print(f"Total features: {total_count}")
    print(f"Processed: {processed}")
    print(f"Saved: {saved}")
    print(f"Errors: {len(errors)}")
    
    if errors:
        print("\nFirst 10 errors:")
        for err in errors[:10]:
            print(f"  - {err}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python import-ridplan-gpkg.py <path-to-gpkg>")
        sys.exit(1)
    
    import_ridplan_to_postgis(sys.argv[1])