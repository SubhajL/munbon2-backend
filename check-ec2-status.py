#!/usr/bin/env python3
import psycopg2

# Connect to EC2
conn = psycopg2.connect(
    host='43.209.12.182',
    port=5432,
    user='postgres',
    password='P@ssw0rd123!',
    database='munbon_dev'
)
cur = conn.cursor()

print("=== CHECKING EC2 munbon_dev DATABASE ===")
print("\nSchemas with table counts:")
cur.execute("""
    SELECT n.nspname as schema_name, COUNT(c.relname) as table_count
    FROM pg_namespace n
    LEFT JOIN pg_class c ON c.relnamespace = n.oid AND c.relkind = 'r'
    WHERE n.nspname NOT IN ('pg_catalog', 'information_schema', 'tiger', 'tiger_data', 'topology')
    GROUP BY n.nspname
    ORDER BY n.nspname;
""")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]} tables")

print("\nChecking key tables for data:")
tables_to_check = [
    ('gis', 'canal_network'),
    ('gis', 'control_structures'), 
    ('gis', 'agricultural_plots'),
    ('ros', 'kc_weekly'),
    ('auth', 'roles')
]

for schema, table in tables_to_check:
    cur.execute(f"SELECT COUNT(*) FROM {schema}.{table}")
    count = cur.fetchone()[0]
    print(f"  {schema}.{table}: {count} rows")

cur.close()
conn.close()

# Check sensor_data
conn = psycopg2.connect(
    host='43.209.12.182',
    port=5432,
    user='postgres',
    password='P@ssw0rd123!',
    database='sensor_data'
)
cur = conn.cursor()

print("\n=== CHECKING EC2 sensor_data DATABASE ===")
print("\nTables in public schema:")
cur.execute("""
    SELECT tablename 
    FROM pg_tables 
    WHERE schemaname = 'public'
    ORDER BY tablename;
""")
for row in cur.fetchall():
    cur.execute(f"SELECT COUNT(*) FROM public.{row[0]}")
    count = cur.fetchone()[0]
    print(f"  public.{row[0]}: {count} rows")

cur.close()
conn.close()