#!/usr/bin/env python3
import psycopg2

print("Testing exact connection that user is using...")
conn = psycopg2.connect(
    host='43.209.12.182',
    port=5432,
    user='postgres',
    password='P@ssw0rd123!',
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