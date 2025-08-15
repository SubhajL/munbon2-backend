#!/usr/bin/env python3
"""Test Scheduler API with EC2 Database"""

import psycopg2
import json
from datetime import datetime, timedelta

# EC2 connection details
EC2_HOST = "43.209.22.250"
EC2_PORT = "5432"
EC2_USER = "postgres"
EC2_PASSWORD = "P@ssw0rd123!"
EC2_DB = "munbon_dev"

def test_scheduler_operations():
    """Test scheduler operations on EC2 database"""
    try:
        conn = psycopg2.connect(
            host=EC2_HOST,
            port=EC2_PORT,
            user=EC2_USER,
            password=EC2_PASSWORD,
            database=EC2_DB
        )
        conn.autocommit = True
        cur = conn.cursor()
        
        print("🔧 Testing Scheduler Operations on EC2 Database\n")
        
        # 1. Create a weekly schedule
        week = "2024-W01"
        print(f"1. Creating schedule for {week}...")
        
        cur.execute("""
            INSERT INTO scheduler.weekly_schedules 
            (week, status, total_volume_m3, optimization_score)
            VALUES (%s, %s, %s, %s)
            RETURNING id
        """, (week, "generated", 125000.0, 0.87))
        
        schedule_id = cur.fetchone()[0]
        print(f"   ✅ Created schedule ID: {schedule_id}")
        
        # 2. Add operations to the schedule
        print("\n2. Adding operations...")
        
        operations = [
            ("Source->M(0,0)", "open", 2.0, "Team_A", 2),
            ("M(0,0)->M(0,2)", "adjust", 1.5, "Team_A", 2),
            ("M(0,2)->Zone_2", "open", 1.8, "Team_B", 4),
        ]
        
        for gate_id, action, opening, team, days_ahead in operations:
            scheduled_time = datetime.now() + timedelta(days=days_ahead)
            cur.execute("""
                INSERT INTO scheduler.schedule_operations
                (schedule_id, gate_id, action, target_opening_m, scheduled_time, team_assigned)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (schedule_id, gate_id, action, opening, scheduled_time, team))
            print(f"   ✅ Added operation: {gate_id} - {action} to {opening}m")
        
        # 3. Submit demands
        print("\n3. Submitting weekly demands...")
        
        demands = {
            "sections": [
                {"section_id": "Zone_2_A", "demand_m3": 45000, "crop": "rice"},
                {"section_id": "Zone_2_B", "demand_m3": 35000, "crop": "rice"},
                {"section_id": "Zone_5_A", "demand_m3": 45000, "crop": "sugarcane"}
            ]
        }
        
        cur.execute("""
            INSERT INTO scheduler.weekly_demands
            (week, section_demands, total_demand_m3, status)
            VALUES (%s, %s, %s, %s)
            RETURNING id
        """, (week, json.dumps(demands["sections"]), 125000, "submitted"))
        
        demand_id = cur.fetchone()[0]
        print(f"   ✅ Created demand ID: {demand_id}")
        
        # 4. Create team assignments
        print("\n4. Creating team assignments...")
        
        cur.execute("""
            SELECT id, gate_id, team_assigned 
            FROM scheduler.schedule_operations 
            WHERE schedule_id = %s
        """, (schedule_id,))
        
        for op_id, gate_id, team in cur.fetchall():
            cur.execute("""
                INSERT INTO scheduler.team_assignments
                (team_code, operation_id, status)
                VALUES (%s, %s, %s)
            """, (team, op_id, "assigned"))
            print(f"   ✅ Assigned {team} to {gate_id}")
        
        # 5. Update schedule status
        print("\n5. Updating schedule status...")
        cur.execute("""
            UPDATE scheduler.weekly_schedules
            SET status = 'approved', approved_at = NOW()
            WHERE id = %s
        """, (schedule_id,))
        print(f"   ✅ Schedule approved")
        
        # 6. Query and display results
        print("\n6. Querying results...")
        
        # Get schedule summary
        cur.execute("""
            SELECT s.week, s.status, s.total_volume_m3,
                   COUNT(o.id) as operation_count,
                   COUNT(DISTINCT o.team_assigned) as teams_involved
            FROM scheduler.weekly_schedules s
            LEFT JOIN scheduler.schedule_operations o ON s.id = o.schedule_id
            WHERE s.id = %s
            GROUP BY s.id, s.week, s.status, s.total_volume_m3
        """, (schedule_id,))
        
        result = cur.fetchone()
        print(f"\n   📊 Schedule Summary:")
        print(f"      Week: {result[0]}")
        print(f"      Status: {result[1]}")
        print(f"      Total Volume: {result[2]:,.0f} m³")
        print(f"      Operations: {result[3]}")
        print(f"      Teams: {result[4]}")
        
        # Get operation details
        cur.execute("""
            SELECT gate_id, action, target_opening_m, team_assigned, 
                   to_char(scheduled_time, 'Day DD Mon') as scheduled
            FROM scheduler.schedule_operations
            WHERE schedule_id = %s
            ORDER BY scheduled_time
        """, (schedule_id,))
        
        print(f"\n   📋 Operation Details:")
        for op in cur.fetchall():
            print(f"      {op[4]}: {op[0]} - {op[1]} to {op[2]}m (Team: {op[3]})")
        
        cur.close()
        conn.close()
        
        print("\n✅ All scheduler operations tested successfully on EC2 database!")
        print("\n📌 Summary:")
        print(f"   - Created schedule for week: {week}")
        print(f"   - Added {len(operations)} gate operations")
        print(f"   - Submitted demands for 3 sections")
        print(f"   - Created team assignments")
        print(f"   - Schedule is ready for field execution")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        return False

if __name__ == "__main__":
    test_scheduler_operations()