#!/bin/bash

echo "=== Testing Rainfall and Water Level Handling ==="
echo

# 1. Test without rainfall/water level
echo "1. Without rainfall/water level (gross demand only):"
curl -s -X POST http://localhost:3047/api/v1/ros/demand/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "areaId": "TEST-NO-RAIN",
    "areaType": "project",
    "cropType": "rice",
    "cropWeek": 5,
    "calendarWeek": 19,
    "calendarYear": 2025,
    "areaRai": 100
  }' | jq '.data | {
    cropWaterDemandMm,
    cropWaterDemandM3,
    effectiveRainfall,
    waterLevel,
    netWaterDemandMm,
    netWaterDemandM3
  }'

echo -e "\n2. With moderate rainfall (10mm):"
curl -s -X POST http://localhost:3047/api/v1/ros/demand/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "areaId": "TEST-MODERATE-RAIN",
    "areaType": "project",
    "cropType": "rice",
    "cropWeek": 5,
    "calendarWeek": 19,
    "calendarYear": 2025,
    "areaRai": 100,
    "effectiveRainfall": 10,
    "waterLevel": 220
  }' | jq '.data | {
    cropWaterDemandMm,
    effectiveRainfall,
    netWaterDemandMm,
    reduction: (.cropWaterDemandMm - .netWaterDemandMm)
  }'

echo -e "\n3. With heavy rainfall (70mm - exceeds demand):"
curl -s -X POST http://localhost:3047/api/v1/ros/demand/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "areaId": "TEST-HEAVY-RAIN",
    "areaType": "project",
    "cropType": "rice",
    "cropWeek": 5,
    "calendarWeek": 19,
    "calendarYear": 2025,
    "areaRai": 100,
    "effectiveRainfall": 70,
    "waterLevel": 225
  }' | jq '.data | {
    cropWaterDemandMm,
    effectiveRainfall,
    netWaterDemandMm,
    message: (if .netWaterDemandMm == 0 then "No irrigation needed" else "Irrigation needed" end)
  }'

echo -e "\n4. Different water levels (no impact on demand):"
for level in 215 220 225; do
  echo -e "\n   Water Level: $level m"
  curl -s -X POST http://localhost:3047/api/v1/ros/demand/calculate \
    -H "Content-Type: application/json" \
    -d "{
      \"areaId\": \"TEST-LEVEL-$level\",
      \"areaType\": \"project\",
      \"cropType\": \"rice\",
      \"cropWeek\": 5,
      \"calendarWeek\": 19,
      \"calendarYear\": 2025,
      \"areaRai\": 100,
      \"effectiveRainfall\": 0,
      \"waterLevel\": $level
    }" | jq -r '.data | "   Demand: \(.cropWaterDemandMm) mm, Water Level: \(.waterLevel) m"'
done

echo -e "\n5. Calculation Examples:"
echo "   Gross Demand = (Weekly ETo × Kc) + Percolation"
echo "   = (36.27 × 1.38) + 14 = 64.05 mm"
echo ""
echo "   Net Demand = Gross Demand - Effective Rainfall"
echo "   With 10mm rain: 64.05 - 10 = 54.05 mm"
echo "   With 70mm rain: 64.05 - 70 = 0 mm (no negative values)"