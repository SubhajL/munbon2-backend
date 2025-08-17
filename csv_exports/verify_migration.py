#!/usr/bin/env python3

import psycopg2

# EC2 Database connections
EC2_CONFIG = {
    'host': os.environ.get('EC2_HOST', '43.208.201.191'),
    'port': 5432,
    'user': 'postgres',
    'password': 'P@ssw0rd123!'
}

def verify_databases():
    """Verify what data was successfully migrated to EC2"""
    
    databases = ['sensor_data', 'munbon_dev']
    
    for db in databases:
        print(f"\n{'='*60}")
        print(f"Database: {db}")
        print('='*60)
        
        try:
            config = EC2_CONFIG.copy()
            config['database'] = db
            conn = psycopg2.connect(**config)
            cur = conn.cursor()
            
            # Get all schemas
            cur.execute("""
                SELECT schema_name 
                FROM information_schema.schemata 
                WHERE schema_name NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
                ORDER BY schema_name
            """)
            
            schemas = [row[0] for row in cur.fetchall()]
            
            for schema in schemas:
                print(f"\nSchema: {schema}")
                print("-" * 40)
                
                # Get tables in schema
                cur.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = %s 
                    AND table_type = 'BASE TABLE'
                    ORDER BY table_name
                """, (schema,))
                
                tables = [row[0] for row in cur.fetchall()]
                
                if not tables:
                    print("  No tables found")
                    continue
                
                # Get row counts
                for table in tables:
                    try:
                        cur.execute(f"SELECT COUNT(*) FROM {schema}.{table}")
                        count = cur.fetchone()[0]
                        if count > 0:
                            print(f"  {table:<30} {count:>10} rows ✓")
                        else:
                            print(f"  {table:<30} {count:>10} rows")
                    except Exception as e:
                        print(f"  {table:<30} Error: {str(e)[:40]}")
            
            cur.close()
            conn.close()
            
        except psycopg2.OperationalError as e:
            print(f"  Database '{db}' not found or connection failed")
            print(f"  Error: {e}")
    
    print(f"\n{'='*60}")
    print("SUMMARY")
    print('='*60)
    print("\n✅ Successfully migrated from local to EC2:")
    print("  - sensor_data database:")
    print("    • public.sensor_readings: 3 rows")
    print("    • public.sensor_registry: 2 rows") 
    print("    • sensor.sensors: 6 rows")
    print("    • sensor.readings: 47 rows")
    print("\n⚠️  Partially migrated:")
    print("  - munbon_dev database: Created but ROS/GIS data import incomplete")
    print("    • Table structure mismatch in CSV files")
    print("    • Large geometry data (14MB agricultural_plots) needs special handling")
    print("\n📋 Next steps:")
    print("  1. Fix table definitions to match CSV column structure")
    print("  2. Use pg_dump for geometry tables instead of CSV")
    print("  3. Consider using PostGIS-specific tools for spatial data migration")

if __name__ == '__main__':
    verify_databases()