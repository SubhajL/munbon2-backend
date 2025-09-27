#!/bin/bash

echo "=== GeoPackage Import Status Check ==="
echo "Date: $(date)"

# Configuration
EC2_IP="43.208.201.191"
SSH_KEY="~/dev/th-lab01.pem"

ssh -i $SSH_KEY ubuntu@$EC2_IP << 'EOF'
echo "1. Worker Status:"
echo "=================="
pm2 status geopackage-processor

echo ""
echo "2. Upload Directory Contents:"
echo "============================="
ls -la /home/ubuntu/geopackage-uploads/

echo ""
echo "3. Processed Directory Contents:"
echo "================================"
ls -la /home/ubuntu/geopackage-processed/

echo ""
echo "4. Database Import Status:"
echo "=========================="

# Check RID-MS parcels
echo "RID-MS Parcels imported:"
docker exec postgres_timescale_postgis psql -U postgres -d munbon_dev -t -c "
SELECT COUNT(*) as total_parcels,
       COUNT(*) FILTER (WHERE data->>'source' = 'geopackage_processor') as from_worker
FROM gis.parcels;"

# Check water level readings
echo ""
echo "Water Level Readings imported:"
docker exec postgres_timescale_postgis psql -U postgres -d munbon_dev -t -c "
SELECT COUNT(*) as total_readings,
       MIN(reading_date) as earliest,
       MAX(reading_date) as latest
FROM ros_gis.manual_water_level_readings 
WHERE volunteer_name = 'GeoPackage Import';"

echo ""
echo "5. Recent Worker Logs:"
echo "======================"
pm2 logs geopackage-processor --lines 20 --nostream

echo ""
echo "6. Sample Imported Data:"
echo "========================"

echo "Sample RID-MS Parcel:"
docker exec postgres_timescale_postgis psql -U postgres -d munbon_dev -t -c "
SELECT data->'parcel_data'->>'parcel_seq' as parcel_seq,
       data->'parcel_data'->>'zone_area' as zone,
       data->'parcel_data'->>'area_rai' as area_rai,
       data->'parcel_data'->>'plant_id' as plant
FROM gis.parcels 
WHERE data->>'source' = 'geopackage_processor'
ORDER BY id DESC LIMIT 1;"

echo ""
echo "Sample Water Level Reading:"
docker exec postgres_timescale_postgis psql -U postgres -d munbon_dev -t -c "
SELECT plot_id, water_level_m, reading_date, notes
FROM ros_gis.manual_water_level_readings 
WHERE volunteer_name = 'GeoPackage Import'
ORDER BY created_at DESC LIMIT 1;"
EOF

echo ""
echo "=== Status Check Complete ==="