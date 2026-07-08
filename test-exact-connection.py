#!/usr/bin/env python3
import os
import psycopg2

print("Testing exact connection that user is using...")
conn = psycopg2.connect(
    host=os.environ.get('EC2_HOST', os.environ.get('POSTGRES_HOST', 'localhost')),
    port=5432,
    user='postgres',
    password=os.environ.get('POSTGRES_PASSWORD', ''),
    database='sensor_data'
)

cur = conn.cursor()

# Test query on public schema
print("\nQuerying public.sensor_readings:")
cur.execute("SELECT COUNT(*) FROM public.sensor_readings;")
count = cur.fetchone()[0]
print(f"Count: {count}")

if count > 0:
    cur.execute("SELECT * FROM public.sensor_readings LIMIT 1;")
    print("Sample row:", cur.fetchone())

# Test query on sensor schema
print("\nQuerying sensor.sensors:")
cur.execute("SELECT COUNT(*) FROM sensor.sensors;")
count = cur.fetchone()[0]
print(f"Count: {count}")

# Check what container this is
cur.execute("SELECT current_setting('cluster_name');")
cluster = cur.fetchone()[0]
print(f"\nCluster name: {cluster}")

cur.close()
conn.close()