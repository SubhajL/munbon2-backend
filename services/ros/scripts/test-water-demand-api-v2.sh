#!/bin/bash

echo "Testing ROS Water Demand API with Thai Excel Values (v2)"
echo "========================================================"

# Helper function to convert month to approximate week
# May = month 5 = weeks 18-21 (assuming week 1 is first week of January)
# July = month 7 = weeks 27-30

# Test Case 1: Rice Week 5 in May (100 rai)
# May is approximately week 19 (mid-May)
echo -e "\n1. Testing Rice Week 5 in May (100 rai):"
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
    "areaRai": 100
  }' | jq '.'

# Test Case 2: Rice Week 14 in July (1000 rai)
# July is approximately week 28 (mid-July)
echo -e "\n2. Testing Rice Week 14 - Peak Kc (1000 rai):"
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
    "areaRai": 1000
  }' | jq '.'

# Test Case 3: Full Rice Area Week 5 (45,731 rai)
echo -e "\n3. Testing Full Rice Area Week 5 (45,731 rai):"
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
    "areaRai": 45731
  }' | jq '.'

# Test health endpoint
echo -e "\n4. Testing Health Endpoint:"
curl http://localhost:3047/health | jq '.'