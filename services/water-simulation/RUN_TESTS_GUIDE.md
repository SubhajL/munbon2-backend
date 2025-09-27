# Running Tests to See Actual Results

This guide shows how to run tests against real services to see actual data for section water delivery analysis.

## Prerequisites

1. **All services must be running:**
   ```bash
   # Check service health
   curl http://localhost:8007/health  # GIS Service
   curl http://localhost:8005/health  # Flow Monitoring Service
   curl http://localhost:8004/health  # ROS Service
   ```

2. **Environment setup:**
   ```bash
   cd services/water-simulation
   
   # Create test environment file
   cp .env.test.example .env.test
   
   # Edit .env.test with your service URLs
   nano .env.test
   ```

## Running Specific Tests

### 1. Test Section 01-06-02-42 Specifically

```bash
# Run the specific test for section 01-06-02-42
USE_REAL_SERVICES=true pytest tests/real_services/test_single_section_scenario.py::TestSingleSectionScenario::test_specific_section_01_06_02_42 -v -s

# The -s flag shows print outputs
# The -v flag shows verbose test names
```

### 2. Test Any Section with Detailed Output

```bash
# Test creation of single section scenarios
USE_REAL_SERVICES=true pytest tests/real_services/test_single_section_scenario.py::TestSingleSectionScenario::test_create_single_section_scenario -v -s

# Test delivery path tracing
USE_REAL_SERVICES=true pytest tests/real_services/test_single_section_scenario.py::TestSingleSectionScenario::test_delivery_path_tracing -v -s

# Test water calculations for different depths
USE_REAL_SERVICES=true pytest tests/real_services/test_single_section_scenario.py::TestSingleSectionScenario::test_water_requirement_calculation -v -s
```

### 3. Run All Single Section Tests

```bash
# Run all tests in the file
USE_REAL_SERVICES=true pytest tests/real_services/test_single_section_scenario.py -v -s
```

### 4. Run with Custom Section ID

You can modify the test to use a different section:

```bash
# First, edit the test config
export TEST_SECTION_IDS='["01-06-02-42", "your-other-section"]'

# Then run the tests
USE_REAL_SERVICES=true pytest tests/real_services/test_single_section_scenario.py -v -s
```

## Understanding Test Output

The tests will print detailed information:

```
--- Single Section Scenario: 01-06-02-42 ---
Water depth required: 5 cm
Section area: 125.50 hectares
Section water volume: 62,750 m³
Canal fill volume: 85,230 m³
Total water needed: 147,980 m³
Delivery path segments: 12
Total distance: 18.5 km
Estimated travel time: 6.9 hours

--- Delivery Path for 01-06-02-42 ---
1. RESERVOIR_MAIN → CANAL001_START (canal)
2. CANAL001_START → GATE001 (gate)
3. GATE001 → CANAL002_START (canal)
...
```

## Debugging Tips

### If Section Not Found

```bash
# Check if section exists in GIS service
curl http://localhost:8007/api/v1/sections/01-06-02-42

# List sections in a zone
curl http://localhost:8007/api/v1/zones/1/sections
```

### If Tests Fail

1. **Check service logs:**
   ```bash
   docker logs gis-service
   docker logs flow-monitoring-service
   ```

2. **Run with more debugging:**
   ```bash
   USE_REAL_SERVICES=true pytest tests/real_services/test_single_section_scenario.py -v -s --log-cli-level=DEBUG
   ```

3. **Test individual service connections:**
   ```bash
   # Test script to verify services
   python scripts/test_service_connections.py
   ```

## Capturing Test Results

### Save to File

```bash
# Run tests and save output
USE_REAL_SERVICES=true pytest tests/real_services/test_single_section_scenario.py::TestSingleSectionScenario::test_specific_section_01_06_02_42 -v -s > test_results_01-06-02-42.txt 2>&1
```

### Generate HTML Report

```bash
# Install pytest-html
pip install pytest-html

# Run with HTML report
USE_REAL_SERVICES=true pytest tests/real_services/test_single_section_scenario.py --html=report.html --self-contained-html -v
```

## Using Make Commands

The Makefile provides shortcuts:

```bash
# Run all real service tests
make test-real

# Run with verbose output
make test-real-verbose

# Run specific test file
USE_REAL_SERVICES=true pytest tests/real_services/test_single_section_scenario.py -v -s
```

## Expected Results

When successful, you should see:
- Actual section area from GIS service
- Real delivery gate assignments
- Actual canal properties (length, cross-section)
- Calculated water volumes based on real data
- Complete delivery path with actual distances