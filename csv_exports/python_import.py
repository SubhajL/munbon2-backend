#!/usr/bin/env python3

import csv
import psycopg2
import json
from datetime import datetime

# EC2 Database connection
EC2_CONFIG = {
    'host': os.environ.get('EC2_HOST', '43.208.201.191'),
    'port': 5432,
    'user': 'postgres',
    'password': 'P@ssw0rd123!',
    'database': 'sensor_data'
}

def import_sensor_data():
    conn = psycopg2.connect(**EC2_CONFIG)
    cur = conn.cursor()
    
    try:
        # Import public.sensor_readings
        print("Importing public.sensor_readings...")
        
        # First disable triggers
        cur.execute("ALTER TABLE public.sensor_readings DISABLE TRIGGER ALL")
        cur.execute("TRUNCATE TABLE public.sensor_readings")
        
        with open('sensor_data/public_sensor_readings.csv', 'r') as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                cur.execute("""
                    INSERT INTO public.sensor_readings 
                    (time, sensor_id, sensor_type, location_lat, location_lng, value, metadata, quality_score)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    row['time'],
                    row['sensor_id'],
                    row['sensor_type'],
                    float(row['location_lat']),
                    float(row['location_lng']),
                    row['value'],
                    row['metadata'],
                    float(row['quality_score'])
                ))
                count += 1
        
        # Re-enable triggers
        cur.execute("ALTER TABLE public.sensor_readings ENABLE TRIGGER ALL")
        conn.commit()
        print(f"  Imported {count} rows to public.sensor_readings")
        
        # Import sensor.readings
        print("\nImporting sensor.readings...")
        
        # Check if table exists and disable triggers
        cur.execute("""
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM information_schema.tables 
                          WHERE table_schema = 'sensor' AND table_name = 'readings') THEN
                    EXECUTE 'ALTER TABLE sensor.readings DISABLE TRIGGER ALL';
                    EXECUTE 'TRUNCATE TABLE sensor.readings';
                END IF;
            END $$;
        """)
        
        with open('sensor_data/sensor_readings.csv', 'r') as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                cur.execute("""
                    INSERT INTO sensor.readings 
                    (time, sensor_id, value, unit, quality_score, raw_data)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    row['time'],
                    row['sensor_id'],
                    float(row['value']),
                    row['unit'],
                    float(row['quality_score']),
                    row['raw_data']
                ))
                count += 1
        
        # Re-enable triggers
        cur.execute("ALTER TABLE sensor.readings ENABLE TRIGGER ALL")
        conn.commit()
        print(f"  Imported {count} rows to sensor.readings")
        
        # Verify imports
        print("\n=== Verification ===")
        tables = [
            ('public', 'sensor_readings'),
            ('public', 'sensor_registry'),
            ('sensor', 'sensors'),
            ('sensor', 'readings')
        ]
        
        for schema, table in tables:
            cur.execute(f"SELECT COUNT(*) FROM {schema}.{table}")
            count = cur.fetchone()[0]
            print(f"{schema}.{table}: {count} rows")
            
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    import_sensor_data()