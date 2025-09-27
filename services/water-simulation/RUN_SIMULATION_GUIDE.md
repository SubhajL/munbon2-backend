# Complete Simulation Guide - Single FTO Water Delivery

This guide shows how to run the complete end-to-end simulation that calls real services from start to finish.

## Overview

The simulation mimics the weekly water management script flow but focuses on delivering water to a single FTO (Field Turnout) with all other demands set to zero.

## Two Simulation Scripts

### 1. Direct Single FTO Simulation
**Script:** `scripts/run_single_fto_simulation.py`

This script runs a direct simulation showing each step clearly:
- Calls ROS for demand calculation
- Gets delivery path from GIS
- Optimizes gates using Flow service
- Creates delivery timeline

**Usage:**
```bash
# Default: Section 01-06-02-42, 337 rai, 5cm
python scripts/run_single_fto_simulation.py

# Custom section and area
python scripts/run_single_fto_simulation.py 01-06-02-42 337 5
```

### 2. Weekly Simulation Runner
**Script:** `scripts/weekly_simulation_runner.py`

This script mimics the actual weekly script with database persistence:
- Creates scenario in database
- Sets all sections to zero demand except target
- Runs full simulation with state tracking
- Generates weekly report

**Usage:**
```bash
# Run weekly simulation
python scripts/weekly_simulation_runner.py

# Custom parameters
python scripts/weekly_simulation_runner.py 01-06-02-42 337 5
```

## Prerequisites

1. **All services must be running:**
   ```bash
   # Check services
   curl http://localhost:8004/health  # ROS
   curl http://localhost:8005/health  # Flow Monitoring
   curl http://localhost:8006/health  # Gate Control
   curl http://localhost:8007/health  # GIS
   ```

2. **Database setup (for weekly runner):**
   ```bash
   cd services/water-simulation
   alembic upgrade head
   ```

3. **Environment variables:**
   ```bash
   export ROS_SERVICE_URL=http://localhost:8004
   export FLOW_SERVICE_URL=http://localhost:8005
   export GATE_SERVICE_URL=http://localhost:8006
   export GIS_SERVICE_URL=http://localhost:8007
   export DATABASE_URL=postgresql://user:pass@localhost/munbon
   ```

## Simulation Flow

### Phase 1: Demand Calculation (ROS)
- Gets section information from GIS
- Calls ROS for crop water requirements
- Calculates volume for 5cm depth on 337 rai
- Determines hourly flow rate needed

### Phase 2: Path Analysis (GIS)
- Finds delivery gate for section
- Traces path from water source
- Identifies all gates along route
- Calculates total distance

### Phase 3: Gate Optimization (Flow + Gate)
- Gets current gate positions
- Gets gate properties (K1/K2 coefficients)
- Optimizes gate openings for target flow
- Generates gate operation schedule

### Phase 4: Delivery Planning
- Calculates water travel time
- Estimates canal filling volume
- Creates timeline for gate operations
- Tracks water front movement

## Expected Output

### Direct Simulation Output:
```
=== Single FTO Water Delivery Simulation ===
Target: Section 01-06-02-42
Area: 337 rai (53.92 hectares)
Required depth: 5 cm
Date: 2024-03-15

STEP 1: Calculating Water Demand (ROS Service)
--------------------------------------------------
Section 01-06-02-42:
  Original area: 784.38 rai
  FTO area: 337 rai
  Crop type: rice

ROS Calculation Results:
  ETo: 5.20 mm/day
  Crop coefficient (Kc): 1.15
  ETc: 5.98 mm/day
  Percolation: 3.00 mm/day
  Crop week: 8

Water Demand Calculation:
  Current water level: 0.03 m
  Target depth: 5 cm
  Area: 53.92 ha (539,200 m²)
  Water volume needed: 26,960 m³
  Delivery window: 24 hours
  Required flow rate: 1123.33 m³/hour
  Required flow rate: 0.312 m³/s

STEP 2: Tracing Delivery Path (GIS Service)
--------------------------------------------------
Delivery gate: GATE_06_42

Delivery path (12 segments):
  1. RESERVOIR_MAIN → CANAL001_START (canal)
  2. CANAL001_START → GATE001 (gate)
  3. GATE001 → CANAL002_START (canal)
  ...
  12. CANAL006_END → GATE_06_42 (gate)

Total distance: 18.50 km
Gates to operate: 6

STEP 3: Getting Current System State
--------------------------------------------------
GATE001:
  Current opening: 0.50 m
  Status: operational
  Discrete levels: L0, L1, L2, L3, L4

GATE_06_42:
  Current opening: 0.00 m
  Status: operational

STEP 4: Optimizing Gate Operations
--------------------------------------------------
Target demand: 1123.33 m³/hour
Optimization objective: water_efficiency

Optimization Results:
  Efficiency score: 95.2%
  Converged: True

Optimized Gate Schedule:
  GATE001:
    Current: 0.50 m
    Optimized: 1.20 m
    Change: +0.70 m
    Estimated flow: 0.425 m³/s (1530 m³/hour)

STEP 5: Creating Delivery Plan
--------------------------------------------------
Delivery Timeline:
  Start time: 2024-03-15 09:00
  Water travel time: 6.9 hours
  Delivery duration: 24 hours
  Total operation time: 30.9 hours

Water Requirements:
  Section water: 26,960 m³
  Canal filling: 129,500 m³
  Total water: 156,460 m³

Gate Operation Schedule:
  09:00 - Open RESERVOIR_GATE to 2.0m
  09:35 - Open GATE001 to 1.2m
  10:45 - Open GATE002 to 1.0m
  ...
  15:50 - Open GATE_06_42 to 0.8m

  15:50 - Begin water delivery to section
  15:50 - Begin closing gates
```

### Weekly Simulation Output:
```
=== WEEKLY WATER SIMULATION (Single FTO) ===
Week: 10 (2024-03-11)
Target: 01-06-02-42 (337 rai)
============================================================

📊 PHASE 1: WEEKLY DEMAND CALCULATION
----------------------------------------
1.1 Calculating FTO Water Demand
  Section: 01-06-02-42
  Area: 337 rai (53.92 ha)
  Required depth: 5 cm
  Water volume: 26,960 m³
  Crop: rice, Week 8

1.2 Analyzing Delivery Infrastructure
  Delivery gate: GATE_06_42
  Path length: 12 segments
  Canal fill volume: 129,500 m³
  Total water needed: 156,460 m³

1.3 Creating Weekly Scenario
✓ Scenario created: 8f3a2b1c-4d5e-6789-abcd-ef0123456789

1.4 Setting Section Demands
  Target section: 26,960 m³
  Other sections: 45 set to 0 m³

🔍 PHASE 2: SYSTEM STATE ASSESSMENT
----------------------------------------
Checking 6 gates in delivery path:
  GATE001: operational (opening: 0.50m)
  GATE002: operational (opening: 0.30m)
  ...
  GATE_06_42: operational (opening: 0.00m)

System readiness: 6/6 gates operational

⚙️ PHASE 3: GATE OPTIMIZATION
----------------------------------------
Optimizing for weekly delivery:
  Total volume: 156,460 m³
  Hourly rate: 931.31 m³/hour

Optimization results:
  Efficiency score: 92.5%
  Gates to operate: 6

🚀 PHASE 4: SIMULATION EXECUTION
----------------------------------------
Starting simulation engine...

  Day 1 of 7
  Day 2 of 7
  ✓ Water delivery completed at hour 31

✓ Simulation completed

📈 PHASE 5: RESULTS ANALYSIS
----------------------------------------
Analyzing 12 simulation states...

📊 Results Summary:
  Target volume: 26,960 m³
  Water delivered: 26,850 m³
  Delivery efficiency: 99.6%
  Delivery complete: Yes
  Completed at: 2024-03-12 16:00

📄 Report saved: weekly_report_week10_20240315_093045.json
```

## Output Files

Both scripts generate JSON reports with complete details:

1. **Direct simulation:** `simulation_results_01-06-02-42_[timestamp].json`
2. **Weekly runner:** `weekly_report_week10_[timestamp].json`

## Troubleshooting

### Service Connection Errors
```bash
# Test connections
python cli/water_delivery_cli.py test-connections
```

### Section Not Found
```bash
# List available sections
python cli/water_delivery_cli.py list-sections 6
```

### Database Issues (Weekly Runner)
```bash
# Check database connection
psql $DATABASE_URL -c "SELECT version();"

# Reset database
alembic downgrade base
alembic upgrade head
```

## Key Differences from Production

1. **Single FTO Only:** Focuses on one 337 rai area instead of full sections
2. **Zero Demands:** All other sections set to zero demand
3. **Simplified Physics:** Uses estimated water velocities and fill ratios
4. **Mock Sensors:** Water levels are estimated, not from real sensors

## Next Steps

After running the simulation:
1. Review the JSON output files for detailed results
2. Check gate operation timeline feasibility
3. Verify water volume calculations
4. Compare with actual field operations