#!/usr/bin/env python3

import psycopg2
import sys
from datetime import datetime

# Local database
LOCAL_CONFIG = {
    'host': 'localhost',
    'port': 5434,
    'database': 'munbon_dev',
    'user': 'postgres',
    'password': 'postgres'
}

# EC2 database
EC2_CONFIG = {
    'host': '43.209.22.250',
    'port': 5432,
    'database': 'munbon_dev',
    'user': 'postgres',
    'password': 'P@ssw0rd123!'
}

def migrate_ros_tables():
    print("=== MIGRATING ROS TABLES TO EC2 ===")
    
    # Connect to both databases
    local_conn = psycopg2.connect(**LOCAL_CONFIG)
    ec2_conn = psycopg2.connect(**EC2_CONFIG)
    
    local_cur = local_conn.cursor()
    ec2_cur = ec2_conn.cursor()
    
    try:
        # Create schemas on EC2
        print("\n1. Creating schemas on EC2...")
        ec2_cur.execute("CREATE SCHEMA IF NOT EXISTS ros;")
        ec2_cur.execute("CREATE SCHEMA IF NOT EXISTS gis;")
        ec2_conn.commit()
        
        # Get list of ROS tables
        local_cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'ros' 
              AND table_type = 'BASE TABLE'
            ORDER BY 
              CASE 
                WHEN table_name = 'plots' THEN 1
                WHEN table_name = 'plot_crop_schedule' THEN 2
                WHEN table_name = 'plot_water_demand_weekly' THEN 3
                WHEN table_name = 'plot_water_demand_seasonal' THEN 4
                ELSE 5
              END,
              table_name
        """)
        tables = [row[0] for row in local_cur.fetchall()]
        
        print(f"\nFound {len(tables)} tables to migrate: {', '.join(tables)}")
        
        # Migrate each table
        for table in tables:
            print(f"\n2. Migrating ros.{table}...")
            
            # Get table structure
            local_cur.execute(f"""
                SELECT column_name, data_type, character_maximum_length, 
                       numeric_precision, numeric_scale, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_schema = 'ros' AND table_name = '{table}'
                ORDER BY ordinal_position
            """)
            columns = local_cur.fetchall()
            
            # Create table on EC2
            create_sql = f"DROP TABLE IF EXISTS ros.{table} CASCADE;\n"
            create_sql += f"CREATE TABLE ros.{table} (\n"
            
            col_defs = []
            col_names = []
            for col in columns:
                col_name, data_type, char_len, num_prec, num_scale, nullable, default = col
                col_names.append(col_name)
                
                # Build column definition
                if data_type == 'character varying' and char_len:
                    col_type = f"VARCHAR({char_len})"
                elif data_type == 'numeric' and num_prec:
                    col_type = f"DECIMAL({num_prec},{num_scale})"
                elif data_type == 'timestamp without time zone':
                    col_type = "TIMESTAMP"
                elif data_type == 'USER-DEFINED':
                    col_type = "GEOMETRY"
                else:
                    col_type = data_type.upper()
                
                col_def = f"    {col_name} {col_type}"
                if nullable == 'NO':
                    col_def += " NOT NULL"
                if default:
                    col_def += f" DEFAULT {default}"
                    
                col_defs.append(col_def)
            
            create_sql += ",\n".join(col_defs) + "\n);"
            
            ec2_cur.execute(create_sql)
            
            # Copy data
            local_cur.execute(f"SELECT COUNT(*) FROM ros.{table}")
            count = local_cur.fetchone()[0]
            print(f"   Copying {count} records...")
            
            if count > 0:
                # Fetch all data
                local_cur.execute(f"SELECT * FROM ros.{table}")
                
                # Insert in batches
                batch_size = 1000
                batch = []
                total_inserted = 0
                
                for row in local_cur:
                    batch.append(row)
                    if len(batch) >= batch_size:
                        placeholders = ','.join(['%s'] * len(col_names))
                        insert_sql = f"INSERT INTO ros.{table} ({','.join(col_names)}) VALUES ({placeholders})"
                        ec2_cur.executemany(insert_sql, batch)
                        total_inserted += len(batch)
                        print(f"   Inserted {total_inserted}/{count} records...")
                        batch = []
                
                # Insert remaining records
                if batch:
                    placeholders = ','.join(['%s'] * len(col_names))
                    insert_sql = f"INSERT INTO ros.{table} ({','.join(col_names)}) VALUES ({placeholders})"
                    ec2_cur.executemany(insert_sql, batch)
                    total_inserted += len(batch)
                
                print(f"   ✓ Migrated {total_inserted} records")
            
            ec2_conn.commit()
        
        # Also migrate gis.ros_water_demands if exists
        local_cur.execute("""
            SELECT 1 FROM information_schema.tables 
            WHERE table_schema='gis' AND table_name='ros_water_demands'
        """)
        if local_cur.fetchone():
            print("\n3. Migrating gis.ros_water_demands...")
            
            # Create table
            ec2_cur.execute("""
                DROP TABLE IF EXISTS gis.ros_water_demands CASCADE;
                CREATE TABLE gis.ros_water_demands (
                    id SERIAL PRIMARY KEY,
                    plot_id VARCHAR(255),
                    zone_name VARCHAR(255),
                    section_name VARCHAR(255),
                    plot_code VARCHAR(255),
                    area_rai DECIMAL,
                    crop_type VARCHAR(100),
                    planting_date DATE,
                    crop_age_days INTEGER,
                    weekly_demand_m3 DECIMAL,
                    monthly_demand_m3 DECIMAL,
                    irrigation_efficiency DECIMAL,
                    calculation_date TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # Copy data
            local_cur.execute("SELECT * FROM gis.ros_water_demands")
            data = local_cur.fetchall()
            if data:
                ec2_cur.executemany("""
                    INSERT INTO gis.ros_water_demands 
                    (id, plot_id, zone_name, section_name, plot_code, area_rai, 
                     crop_type, planting_date, crop_age_days, weekly_demand_m3, 
                     monthly_demand_m3, irrigation_efficiency, calculation_date, 
                     created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, data)
                print(f"   ✓ Migrated {len(data)} records")
            
            ec2_conn.commit()
        
        # Create constraints and indexes
        print("\n4. Creating constraints and indexes...")
        ec2_cur.execute("""
            -- Add primary keys
            ALTER TABLE ros.plots ADD PRIMARY KEY (id) IF NOT EXISTS;
            ALTER TABLE ros.plot_crop_schedule ADD PRIMARY KEY (id) IF NOT EXISTS;
            ALTER TABLE ros.plot_water_demand_weekly ADD PRIMARY KEY (id) IF NOT EXISTS;
            ALTER TABLE ros.plot_water_demand_seasonal ADD PRIMARY KEY (id) IF NOT EXISTS;
            
            -- Add foreign keys
            ALTER TABLE ros.plot_crop_schedule 
                ADD CONSTRAINT plot_crop_schedule_plot_id_fkey 
                FOREIGN KEY (plot_id) REFERENCES ros.plots(plot_id);
                
            ALTER TABLE ros.plot_water_demand_weekly 
                ADD CONSTRAINT plot_water_demand_weekly_plot_id_fkey 
                FOREIGN KEY (plot_id) REFERENCES ros.plots(plot_id);
                
            ALTER TABLE ros.plot_water_demand_seasonal 
                ADD CONSTRAINT plot_water_demand_seasonal_plot_id_fkey 
                FOREIGN KEY (plot_id) REFERENCES ros.plots(plot_id);
        """)
        
        ec2_conn.commit()
        
        # Verify migration
        print("\n5. Verifying migration...")
        ec2_cur.execute("""
            SELECT 
                schemaname,
                tablename,
                n_live_tup as rows
            FROM pg_stat_user_tables
            WHERE schemaname IN ('ros', 'gis')
            ORDER BY schemaname, tablename
        """)
        
        print("\nTable counts on EC2:")
        for row in ec2_cur.fetchall():
            print(f"   {row[0]}.{row[1]}: {row[2]} rows")
        
        print("\n✅ Migration complete!")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        ec2_conn.rollback()
        sys.exit(1)
    finally:
        local_cur.close()
        ec2_cur.close()
        local_conn.close()
        ec2_conn.close()

if __name__ == "__main__":
    migrate_ros_tables()