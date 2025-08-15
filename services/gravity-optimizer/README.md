# Gravity Flow Optimizer Service

Optimizes water delivery through the Munbon irrigation system using gravity-fed constraints. This service ensures efficient water distribution while respecting physical limitations of the canal network.

## Overview

The Gravity Flow Optimizer performs:
- **Elevation Feasibility Analysis**: Verifies water can reach all zones by gravity
- **Minimum Depth Calculation**: Ensures adequate flow depths for stable operation
- **Flow Split Optimization**: Distributes water through 20 automated gates
- **Delivery Sequencing**: Orders deliveries to minimize travel time
- **Energy Recovery Analysis**: Identifies micro-hydro potential
- **Contingency Planning**: Prepares for common failure scenarios

## Key Features

### 1. Elevation Feasibility Checker
- Verifies gravity delivery is possible to each zone
- Calculates minimum required source water levels
- Identifies critical channel sections
- Accounts for head losses along flow paths

### 2. Minimum Depth Calculator
- Ensures flow depths prevent sedimentation (min velocity: 0.3 m/s)
- Prevents erosion (max velocity: 2.0 m/s)
- Maintains stable flow conditions (avoids critical flow)
- Provides operational depth recommendations

### 3. Flow Splitter
- Optimizes settings for 20 automated gates
- Supports multiple objectives:
  - Minimize travel time
  - Maximize delivery efficiency
  - Minimize energy losses
  - Balanced approach
- Handles over-allocation scenarios gracefully

### 4. Energy Recovery
- Identifies drops > 2m suitable for micro-hydro
- Estimates power generation potential
- Provides feasibility assessments
- Calculates payback periods

## Physical Constraints

- **No pumps**: Entirely gravity-fed system
- **Bed slopes**: 0.0001 to 0.0002 (very gentle)
- **Minimum flow depth**: 0.3m (with 1.2x safety factor)
- **Maximum velocity**: 2.0 m/s (erosion prevention)
- **Source elevation**: 221m MSL
- **Zone elevations**: 215-219m MSL

## API Endpoints

### Main Optimization
```
POST /api/v1/gravity-optimizer/optimize
```
Performs complete optimization including feasibility, flow splits, and sequencing.

### Feasibility Check
```
POST /api/v1/gravity-optimizer/feasibility/check
GET  /api/v1/gravity-optimizer/feasibility/{zone_id}
```
Check if zones can receive water by gravity.

### Depth Requirements
```
POST /api/v1/gravity-optimizer/depth/calculate
```
Calculate minimum depths for channels.

### Flow Distribution
```
POST /api/v1/gravity-optimizer/flow-split/optimize
```
Optimize gate settings for desired flows.

### Energy Recovery
```
GET /api/v1/gravity-optimizer/energy-recovery/potential
```
Identify micro-hydro opportunities.

### Contingency Plans
```
GET /api/v1/gravity-optimizer/contingency/plans
```
Get plans for failure scenarios.

## Installation

1. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the service:
```bash
python -m uvicorn src.main:app --host 0.0.0.0 --port 3020 --reload
```

## Testing

Run the test script:
```bash
python test_optimizer.py
```

## Configuration

Edit `src/config/settings.py` or use environment variables:
- `GRAVITY_PORT`: Service port (default: 3020)
- `GRAVITY_POSTGRES_HOST`: Database host
- `GRAVITY_REDIS_HOST`: Redis cache host
- `GRAVITY_LOG_LEVEL`: Logging level

## Integration with BFF

This service integrates with the BFF (Backend for Frontend) service on port 3020. The BFF aggregates results from multiple services including this optimizer.

## Algorithms Used

1. **Manning's Equation**: For hydraulic calculations
2. **Newton-Raphson Method**: For flow depth iterations
3. **Sequential Quadratic Programming (SLSQP)**: For gate optimization
4. **Dynamic Programming**: For delivery sequencing
5. **Monte Carlo Simulation**: For contingency planning (planned)

## Future Enhancements

- [ ] Real-time gate position feedback
- [ ] Machine learning for flow predictions
- [ ] Integration with weather forecasts
- [ ] Sediment transport modeling
- [ ] Automated contingency activation
- [ ] Mobile app integration