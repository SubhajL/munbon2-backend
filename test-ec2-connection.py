#!/usr/bin/env python3
import psycopg2
import sys

# Connection parameters
conn_params = {
    'host': '43.209.12.182',
    'port': 5432,
    'user': 'postgres',
    'password': 'P@ssw0rd123!',
    'database': 'postgres'
}

try:
    # Connect to PostgreSQL
    print("Connecting to PostgreSQL...")
    conn = psycopg2.connect(**conn_params)
    cur = conn.cursor()
    
    # Get version
    cur.execute("SELECT version();")
    version = cur.fetchone()[0]
    print(f"Connected successfully!\nVersion: {version}\n")
    
    # List databases
    print("Databases:")
    cur.execute("SELECT datname FROM pg_database WHERE datistemplate = false ORDER BY datname;")
    databases = cur.fetchall()
    for db in databases:
        print(f"  - {db[0]}")
    
    # Check sensor_data specifically
    print("\nChecking sensor_data database...")
    conn.close()
    
    # Connect to sensor_data
    conn_params['database'] = 'sensor_data'
    conn = psycopg2.connect(**conn_params)
    cur = conn.cursor()
    
    # List schemas
    cur.execute("""
        SELECT schema_name 
        FROM information_schema.schemata 
        WHERE schema_name NOT IN ('pg_catalog', 'information_schema')
        ORDER BY schema_name;
    """)
    schemas = cur.fetchall()
    print("Schemas in sensor_data:")
    for schema in schemas:
        print(f"  - {schema[0]}")
    
    # Count tables in public schema
    cur.execute("""
        SELECT COUNT(*) 
        FROM information_schema.tables 
        WHERE table_schema = 'public';
    """)
    table_count = cur.fetchone()[0]
    print(f"\nTables in public schema: {table_count}")
    
    cur.close()
    conn.close()
    
except Exception as e:
    print(f"Connection failed: {e}")
    sys.exit(1)

print("\nConnection details for your database client:")
print(f"Host: {conn_params['host']}")
print(f"Port: {conn_params['port']}")
print(f"Username: {conn_params['user']}")
print(f"Password: {conn_params['password']}")
print("Database: sensor_data (or any from the list above)")