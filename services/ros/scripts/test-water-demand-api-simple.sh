#!/bin/bash

echo "Testing ROS Water Demand API - Simple Test (No Rainfall/Water Level)"
echo "===================================================================="

# Test Case 1: Rice Week 5 in May (100 rai) - WITH rainfall and water level
echo -e "\n1. Testing Rice Week 5 in May (100 rai) - With explicit values:"
echo "Expected: 39.677 mm, 6,348 m³"
curl -X POST http://localhost:3047/api/v1/ros/demand/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "areaId": "THAI-TEST-01",
    "areaType": "project",
    "cropType": "rice",
    "cropWeek": 5,
    "calendarWeek": 19,
    "calendarYear": 2025,
    "areaRai": 100,
    "effectiveRainfall": 0,
    "waterLevel": 220
  }' | jq '.'

# Test Case 2: Rice Week 14 in July (1000 rai) - With explicit values
echo -e "\n2. Testing Rice Week 14 - Peak Kc (1000 rai) - With explicit values:"
echo "Expected: 53.324 mm, 85,319 m³"
curl -X POST http://localhost:3047/api/v1/ros/demand/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "areaId": "THAI-TEST-02",
    "areaType": "project",
    "cropType": "rice", 
    "cropWeek": 14,
    "calendarWeek": 28,
    "calendarYear": 2025,
    "areaRai": 1000,
    "effectiveRainfall": 0,
    "waterLevel": 220
  }' | jq '.'

# Test Case 3: Full Rice Area Week 5 (45,731 rai) - With explicit values
echo -e "\n3. Testing Full Rice Area Week 5 (45,731 rai) - With explicit values:"
echo "Expected: 39.677 mm, 2,903,150 m³"
curl -X POST http://localhost:3047/api/v1/ros/demand/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "areaId": "MUNBON-PROJECT",
    "areaType": "project",
    "cropType": "rice",
    "cropWeek": 5,
    "calendarWeek": 19,
    "calendarYear": 2025,
    "areaRai": 45731,
    "effectiveRainfall": 0,
    "waterLevel": 220
  }' | jq '.'

echo -e "\n4. Calculation Details:"
echo "- Weekly ETo (May) = 142.65 ÷ 4 = 35.66 mm/week"
echo "- Rice Week 5 Kc = 0.72"
echo "- Water Demand = (35.66 × 0.72) + 14 = 39.68 mm"
echo "- Volume = 39.68 × area × 1.6"