#!/usr/bin/env python3
"""Test EC2 PostgreSQL Connection"""

import psycopg2
import sys

# EC2 connection details
EC2_HOST = os.environ.get('EC2_HOST', '43.208.201.191')
EC2_PORT = "5432"
EC2_USER = "postgres"
EC2_PASSWORD = "P@ssw0rd123!"
EC2_DB = "munbon_dev"

def test_connection():
    """Test connection to EC2 PostgreSQL"""
    try:
        print(f"Connecting to PostgreSQL at {EC2_HOST}:{EC2_PORT}...")
        
        # Connect to database
        conn = psycopg2.connect(
            host=EC2_HOST,
            port=EC2_PORT,
            user=EC2_USER,
            password=EC2_PASSWORD,
            database=EC2_DB
        )
        
        print("✅ Connection successful!")
        
        # Test query
        cur = conn.cursor()
        
        # Check version
        cur.execute("SELECT version()")
        version = cur.fetchone()[0]
        print(f"\nPostgreSQL Version:\n{version}")
        
        # Check scheduler schema
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'scheduler'
            ORDER BY table_name
        """)
        
        tables = cur.fetchall()
        print(f"\nScheduler Schema Tables ({len(tables)}):")
        for table in tables:
            print(f"  - {table[0]}")
        
        # Check teams
        cur.execute("SELECT team_code, team_name FROM scheduler.field_teams")
        teams = cur.fetchall()
        print(f"\nField Teams ({len(teams)}):")
        for team in teams:
            print(f"  - {team[0]}: {team[1]}")
        
        # Check if any schedules exist
        cur.execute("SELECT COUNT(*) FROM scheduler.weekly_schedules")
        schedule_count = cur.fetchone()[0]
        print(f"\nWeekly Schedules: {schedule_count}")
        
        cur.close()
        conn.close()
        
        print("\n✅ All tests passed! EC2 database is ready for scheduler service.")
        return True
        
    except Exception as e:
        print(f"\n❌ Connection failed: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)