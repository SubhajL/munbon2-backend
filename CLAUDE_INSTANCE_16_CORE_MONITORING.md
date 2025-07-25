# Claude Instance 16: Core Flow Monitoring with Dual-Mode Control

## Context
You are implementing Tasks 50, 59, and 65 for the Munbon Irrigation Backend project. This is the CRITICAL PATH - other teams depend on your implementation. The system must support both real-time automated control (20 gates) and weekly batch manual operations seamlessly.

## Your Task Sequence

### Phase 1: Task 50 - Flow/Volume/Level Monitoring Service
Implement the core monitoring service with dual-mode support.

**Key Features:**
1. Calibrated gate flow equations: Q = Cs × L × Hs × √(2g × ΔH)
   - Cs = K1 × (Hs/Go)^K2 (gate-specific calibration)
2. Iterative hydraulic solver for network-wide water levels
3. Path-based flow calculator for multi-zone deliveries
4. Temporal scheduler with travel time calculations
5. Dynamic flow reduction algorithms
6. Confidence scoring for ungauged locations

**Technical Requirements:**
- Python/FastAPI on port 3011
- InfluxDB for real-time data
- TimescaleDB for aggregations
- Support both continuous and batch queries

### Phase 2: Task 59 - Dual-Mode Gate Control System
Add unified control for automated and manual gates.

**Key Features:**
1. Gate classification system (automated/manual/hybrid)
2. Real-time PID control for automated gates
3. Manual instruction generator considering automated states
4. Synchronization protocol preventing conflicts
5. Fallback procedures for automated gate failures
6. Unified state tracking across both modes

### Phase 3: Task 65 - Mode Transition System
Implement seamless transitions between operational modes.

**Key Features:**
1. Automatic mode selection based on conditions
2. State preservation during transitions
3. Gradual transition capabilities
4. Emergency transition protocols
5. Performance tracking in both modes

## Critical Integration Points
- SCADA system for automated gates
- Field team mobile app for manual operations
- ROS/GIS services for demand data
- Weather services for adaptation

## Design Principles
1. **No conflicts**: Manual and automated operations must never conflict
2. **Graceful degradation**: System remains operational with gate failures
3. **State consistency**: Always know the state of every gate
4. **Audit trail**: Complete record of all operations

## Deliverables Priority
1. Core hydraulic solver with calibrated equations
2. Dual-mode gate control APIs
3. Mode transition controller
4. Integration tests for all scenarios
5. Performance benchmarks

## Known Constraints
- Limited sensors (6 water level + 1 moisture)
- Weekly manual operation cycles
- Gravity-fed system (no pumps)
- Section-level control (50-200 hectares)

Start with the hydraulic solver using the corrected gate equation, then build the control layers on top.