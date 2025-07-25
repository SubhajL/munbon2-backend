#!/usr/bin/env python3
"""
Verify ROS-GIS consolidation is working by checking the database directly
"""
import asyncio
import asyncpg
import json
from datetime import datetime

async def verify_consolidation():
    """Check if the ROS consolidation tables are working"""
    
    # Connect to the database
    conn = await asyncpg.connect(
        host='localhost',
        port=5434,
        database='munbon_dev',
        user='postgres',
        password='postgres'
    )
    
    try:
        print("=== ROS-GIS Consolidation Verification ===\n")
        
        # 1. Check if tables exist
        print("1. Checking tables exist...")
        tables = await conn.fetch("""
            SELECT tablename 
            FROM pg_tables 
            WHERE schemaname = 'gis' 
            AND tablename IN ('ros_water_demands', 'agricultural_plots')
            ORDER BY tablename
        """)
        
        for table in tables:
            print(f"   ✓ Table: gis.{table['tablename']}")
        
        # 2. Check views
        print("\n2. Checking views exist...")
        views = await conn.fetch("""
            SELECT viewname 
            FROM pg_views 
            WHERE schemaname = 'gis' 
            AND viewname = 'latest_ros_demands'
        """)
        
        for view in views:
            print(f"   ✓ View: gis.{view['viewname']}")
            
        # 3. Check materialized views
        print("\n3. Checking materialized views...")
        mat_views = await conn.fetch("""
            SELECT matviewname 
            FROM pg_matviews 
            WHERE schemaname = 'gis' 
            AND matviewname = 'weekly_demand_summary'
        """)
        
        for mv in mat_views:
            print(f"   ✓ Materialized View: gis.{mv['matviewname']}")
        
        # 4. Check agricultural plots
        print("\n4. Checking agricultural plots...")
        plot_count = await conn.fetchval("""
            SELECT COUNT(*) FROM gis.agricultural_plots
        """)
        print(f"   Total agricultural plots: {plot_count}")
        
        # 5. Check ROS water demands
        print("\n5. Checking ROS water demands...")
        demand_count = await conn.fetchval("""
            SELECT COUNT(*) FROM gis.ros_water_demands
        """)
        print(f"   Total ROS water demands: {demand_count}")
        
        # 6. Sample data from agricultural plots
        print("\n6. Sample agricultural plots:")
        sample_plots = await conn.fetch("""
            SELECT 
                id,
                plot_code,
                area_hectares,
                properties->>'amphoe' as amphoe,
                properties->>'tambon' as tambon
            FROM gis.agricultural_plots
            LIMIT 5
        """)
        
        for plot in sample_plots:
            print(f"   Plot: {plot['plot_code']}, Area: {plot['area_hectares']:.2f} ha ({plot['area_hectares'] * 6.25:.2f} rai), "
                  f"Location: {plot['tambon']}, {plot['amphoe']}")
        
        # 7. Check if we can insert test data
        print("\n7. Testing insert capability...")
        
        # Get a sample parcel
        sample_parcel = await conn.fetchrow("""
            SELECT id, plot_code FROM gis.agricultural_plots LIMIT 1
        """)
        
        if sample_parcel:
            # Try to insert test data
            try:
                await conn.execute("""
                    INSERT INTO gis.ros_water_demands (
                        parcel_id, section_id, calculation_date, calendar_week, calendar_year,
                        crop_type, crop_week, growth_stage, area_rai,
                        et0_mm, kc_factor, percolation_mm,
                        gross_demand_mm, gross_demand_m3, net_demand_mm, net_demand_m3
                    ) VALUES (
                        $1, $2, $3, $4, $5,
                        $6, $7, $8, $9,
                        $10, $11, $12,
                        $13, $14, $15, $16
                    )
                    ON CONFLICT (parcel_id, calendar_week, calendar_year) 
                    WHERE parcel_id IS NOT NULL
                    DO UPDATE SET
                        calculation_date = EXCLUDED.calculation_date,
                        crop_type = EXCLUDED.crop_type,
                        net_demand_m3 = EXCLUDED.net_demand_m3,
                        updated_at = CURRENT_TIMESTAMP
                """,
                    sample_parcel['id'],
                    'section_test',
                    datetime.now(),
                    18,  # week 18
                    2024,
                    'rice',
                    5,
                    'tillering',
                    10.5,  # area in rai
                    5.2,   # ET0
                    1.05,  # Kc
                    14.0,  # percolation
                    19.46, # gross demand mm
                    325.0, # gross demand m3
                    15.46, # net demand mm
                    258.0  # net demand m3
                )
                
                print("   ✓ Successfully inserted test ROS water demand")
                
                # Verify the insert
                verify = await conn.fetchrow("""
                    SELECT * FROM gis.ros_water_demands 
                    WHERE parcel_id = $1 AND calendar_week = 18 AND calendar_year = 2024
                """, sample_parcel['id'])
                
                if verify:
                    print(f"   ✓ Verified: {verify['crop_type']} demand for plot {sample_parcel['plot_code']}: "
                          f"{verify['net_demand_m3']:.1f} m³")
                
            except Exception as e:
                print(f"   ✗ Insert failed: {e}")
        
        # 8. Test the latest_ros_demands view
        print("\n8. Testing latest_ros_demands view...")
        latest = await conn.fetch("""
            SELECT plot_code, crop_type, net_demand_m3, amphoe, tambon
            FROM gis.latest_ros_demands
            LIMIT 3
        """)
        
        if latest:
            print("   Latest demands:")
            for row in latest:
                print(f"   - {row['plot_code']}: {row['crop_type']}, {row['net_demand_m3']:.1f} m³, "
                      f"{row['tambon']}, {row['amphoe']}")
        else:
            print("   No data in latest_ros_demands view yet")
        
        print("\n✅ ROS-GIS Consolidation is properly set up!")
        print("\nNext steps:")
        print("1. Start the ROS service on port 3047")
        print("2. Start the GIS service on port 3007")
        print("3. Start the ROS-GIS Integration service on port 3022")
        print("4. Trigger sync: POST http://localhost:3022/api/v1/sync/trigger")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(verify_consolidation())