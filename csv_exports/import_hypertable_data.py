#!/usr/bin/env python3

import csv
import psycopg2
from datetime import datetime

# EC2 Database connection
EC2_CONFIG = {
    'host': os.environ.get('EC2_HOST', '43.208.201.191'),
    'port': 5432,
    'user': 'postgres',
    'password': 'P@ssw0rd123!',
    'database': 'sensor_data'
}

def import_hypertable_data():
    conn = psycopg2.connect(**EC2_CONFIG)
    cur = conn.cursor()
    
    try:
        # Import water_level_readings
        print("Importing water_level_readings...")
        
        # Disable triggers
        cur.execute("ALTER TABLE public.water_level_readings DISABLE TRIGGER ALL")
        cur.execute("TRUNCATE TABLE public.water_level_readings")
        
        with open('sensor_data/water_level_readings_full.csv', 'r') as f:
            reader = csv.DictReader(f)
            count = 0
            batch = []
            
            for row in reader:
                def safe_float(value):
                    return float(value) if value and value.strip() else None
                
                def safe_int(value):
                    return int(value) if value and value.strip() else None
                
                batch.append((
                    row['time'],
                    row['sensor_id'],
                    safe_float(row['location_lat']),
                    safe_float(row['location_lng']),
                    safe_float(row['level_cm']),
                    safe_float(row['voltage']),
                    safe_int(row['rssi']),
                    safe_float(row['temperature']),
                    safe_float(row['quality_score'])
                ))
                
                # Insert in batches of 1000
                if len(batch) >= 1000:
                    cur.executemany("""
                        INSERT INTO public.water_level_readings 
                        (time, sensor_id, location_lat, location_lng, level_cm, voltage, rssi, temperature, quality_score)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, batch)
                    count += len(batch)
                    batch = []
                    print(f"  Imported {count} rows...")
            
            # Insert remaining batch
            if batch:
                cur.executemany("""
                    INSERT INTO public.water_level_readings 
                    (time, sensor_id, location_lat, location_lng, level_cm, voltage, rssi, temperature, quality_score)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, batch)
                count += len(batch)
        
        # Re-enable triggers
        cur.execute("ALTER TABLE public.water_level_readings ENABLE TRIGGER ALL")
        conn.commit()
        print(f"  Total imported: {count} rows to water_level_readings")
        
        # Import moisture_readings
        print("\nImporting moisture_readings...")
        
        # Disable triggers
        cur.execute("ALTER TABLE public.moisture_readings DISABLE TRIGGER ALL")
        cur.execute("TRUNCATE TABLE public.moisture_readings")
        
        with open('sensor_data/moisture_readings_full.csv', 'r') as f:
            reader = csv.DictReader(f)
            count = 0
            
            for row in reader:
                cur.execute("""
                    INSERT INTO public.moisture_readings 
                    (time, sensor_id, location_lat, location_lng, moisture_surface_pct, 
                     moisture_deep_pct, temp_surface_c, temp_deep_c, ambient_humidity_pct, 
                     ambient_temp_c, flood_status, voltage, quality_score)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    row['time'],
                    row['sensor_id'],
                    float(row['location_lat']),
                    float(row['location_lng']),
                    float(row['moisture_surface_pct']),
                    float(row['moisture_deep_pct']),
                    float(row['temp_surface_c']),
                    float(row['temp_deep_c']),
                    float(row['ambient_humidity_pct']),
                    float(row['ambient_temp_c']),
                    row['flood_status'] == 't',
                    float(row['voltage']),
                    float(row['quality_score'])
                ))
                count += 1
        
        # Re-enable triggers
        cur.execute("ALTER TABLE public.moisture_readings ENABLE TRIGGER ALL")
        conn.commit()
        print(f"  Total imported: {count} rows to moisture_readings")
        
        # Final verification
        print("\n=== Verification ===")
        tables = [
            'sensor_readings',
            'sensor_registry',
            'water_level_readings',
            'moisture_readings'
        ]
        
        for table in tables:
            cur.execute(f"SELECT COUNT(*) FROM public.{table}")
            count = cur.fetchone()[0]
            print(f"public.{table}: {count} rows")
        
        # Also check sensor schema
        print("\nSensor schema:")
        for table in ['sensors', 'readings']:
            cur.execute(f"SELECT COUNT(*) FROM sensor.{table}")
            count = cur.fetchone()[0]
            print(f"sensor.{table}: {count} rows")
            
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    import_hypertable_data()