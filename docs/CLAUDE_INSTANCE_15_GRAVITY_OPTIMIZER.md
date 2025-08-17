# Claude Instance 15: Gravity Flow Optimizer

## Context
You are implementing Task 64 for the Munbon Irrigation Backend project. The entire system is gravity-fed with specific bed slopes. You must optimize water delivery considering elevation constraints, using automated gates for fine control while manual gates handle major routing.

## Your Task
Implement the Gravity Flow Optimizer that ensures efficient water delivery through a gravity-fed network.

## Key Requirements

### Physical Constraints
- No pumps - entirely gravity fed
- Bed slopes: 0.0001 to 0.0002 (very gentle)
- Minimum flow depths required
- Cannot reverse flow direction

### Optimization Goals
1. **Elevation Feasibility**
   - Verify all sections can receive water by gravity
   - Calculate minimum required upstream levels
   - Identify hydraulically challenged areas

2. **Flow Splitting**
   - Use 20 automated gates for precise flow division
   - Manual gates for major routing decisions
   - Optimize split ratios for multiple zones

3. **Travel Time Minimization**
   - Calculate optimal flow rates for quick delivery
   - Balance speed vs capacity constraints
   - Consider varying channel roughness

4. **Sequencing Optimization**
   - Determine best order for zone deliveries
   - Minimize water residence time
   - Prevent stagnation in channels

### Technical Specifications
- Python/NumPy/SciPy for optimization
- Port: 3020 (as BFF service extension)
- Integration with hydraulic solver
- PostGIS for elevation data

### Deliverables
1. Gravity feasibility checker
2. Optimal flow splitting algorithm
3. Delivery sequence optimizer
4. Minimum depth calculator
5. Energy recovery identifier (micro-hydro potential)
6. Contingency routing planner

### Key Algorithms
- Network flow optimization
- Dynamic programming for sequencing
- Gradient-based optimization for splits
- Monte Carlo for contingency planning

### Elevation Data
```
Source: 221m MSL
Zone 1: 218-219m
Zone 2: 217-218m
Zone 3: 217-217.5m
Zone 4: 216-217m
Zone 5: 215-216m
Zone 6: 215-216m
```

## Implementation Notes
- Account for head losses in long channels
- Consider sediment deposition effects
- Handle dry channel startup conditions
- Provide safety margins for minimum depths
- Identify potential hydraulic jumps

Start by implementing the elevation feasibility checker and minimum depth calculator.