#!/bin/bash

echo "Testing ROS Water Demand API with Thai Excel Values"
echo "===================================================="

# Test Case 1: Rice Week 5 in May (100 rai)
echo -e "\n1. Testing Rice Week 5 in May (100 rai):"
echo "Expected: 39.677 mm, 6,348 m³"
curl -X POST http://localhost:3047/api/v1/ros/demand/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "areaId": "THAI-TEST-01",
    "cropType": "rice",
    "cropWeek": 5,
    "calendarMonth": 5,
    "areaRai": 100
  }' | jq '.'

# Test Case 2: Rice Week 14 in July (1000 rai)
echo -e "\n2. Testing Rice Week 14 - Peak Kc (1000 rai):"
echo "Expected: 53.324 mm, 85,319 m³"
curl -X POST http://localhost:3047/api/v1/ros/demand/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "areaId": "THAI-TEST-02",
    "cropType": "rice", 
    "cropWeek": 14,
    "calendarMonth": 7,
    "areaRai": 1000
  }' | jq '.'

# Test Case 3: Full Rice Area Week 5 (45,731 rai)
echo -e "\n3. Testing Full Rice Area Week 5 (45,731 rai):"
echo "Expected: 39.677 mm, 2,903,150 m³"
curl -X POST http://localhost:3047/api/v1/ros/demand/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "areaId": "MUNBON-PROJECT",
    "cropType": "rice",
    "cropWeek": 5,
    "calendarMonth": 5,
    "areaRai": 45731
  }' | jq '.'