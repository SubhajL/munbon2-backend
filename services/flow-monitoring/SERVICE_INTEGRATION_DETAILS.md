# Detailed Service Integration Explanation

## Core Concept: Service Responsibilities and Data Flow

### 1. Flow Monitoring Service (THIS SERVICE - Port 3011)

**Role: Real-time Hydraulic State Manager & Control Coordinator**

This service is the **central nervous system** for real-time hydraulic monitoring and control. It maintains the current state of the entire irrigation network.

**What it PROVIDES to other services:**
```
TO → Gravity Optimization Service:
- Current water levels at all nodes
- Current gate positions and flows
- System constraints (max flows, min levels)
- Network capacity analysis
- What-if simulation results

TO → Scheduled Field Operations:
- Manual gate current positions
- Travel time calculations
- Flow impact predictions
- Historical performance data

TO → SCADA Integration:
- Gate control commands
- Emergency stop signals
- Mode transition notifications
```

**What it CONSUMES from other services:**
```
FROM ← Gravity Optimization:
- Optimal gate settings
- Target flows by zone
- Priority rankings
- Constraint adjustments

FROM ← Scheduled Field Operations:
- Manual gate schedules
- Completed work orders
- Field team updates
- Maintenance windows

FROM ← SCADA Integration:
- Real-time gate positions
- Equipment status
- Fault notifications
- Sensor readings
```

### 2. Gravity Optimization Service (Port 3010)

**Role: Strategic Water Distribution Planner**

This service performs complex optimization to determine the best water distribution strategy.

**Key Functions:**
- Multi-objective optimization (efficiency, equity, reliability)
- Demand-supply matching
- Energy minimization (using gravity efficiently)
- Conflict resolution between competing demands

**Integration Pattern:**
```
Every 5 minutes (or on-demand):
1. Queries Flow Monitoring for current state
2. Gets farmer demands from database
3. Runs optimization algorithms
4. Sends optimal settings back to Flow Monitoring
5. Flow Monitoring implements via SCADA or Field Ops
```

### 3. Scheduled Field Operation Service (Port 3031)

**Role: Manual Operations Coordinator**

Manages all manual gate operations through field teams.

**Key Functions:**
- Weekly operation planning
- Work order generation
- Field team scheduling
- Progress tracking
- Manual update collection

**Integration Pattern:**
```
Weekly Cycle:
Monday 6:00 AM:
1. Get optimization targets from Gravity Optimizer
2. Query Flow Monitoring for current manual gate states
3. Calculate required adjustments
4. Generate work orders with priorities
5. Assign to field teams via mobile app

During Week:
- Receives updates from field teams
- Notifies Flow Monitoring of completed adjustments
- Tracks deviations from plan
- Requests re-optimization if needed
```

### 4. SCADA Integration Service (Port 3015)

**Role: Hardware Communication Bridge**

Translates between internal services and GE iFix SCADA system.

**Key Functions:**
- OPC UA protocol handling
- Command queuing and execution
- Status monitoring
- Fault detection
- Data acquisition

## Critical Integration Scenarios

### Scenario 1: Normal Automated Operation
```
Time 0ms: Sensor detects low water level in Zone 3
Time 10ms: Flow Monitoring receives sensor data
Time 50ms: Flow Monitoring updates hydraulic state
Time 100ms: Gravity Optimizer notified of state change
Time 5s: Gravity Optimizer completes optimization
Time 5.1s: New gate settings sent to Flow Monitoring
Time 5.2s: Flow Monitoring validates and sends to SCADA
Time 5.5s: SCADA Integration executes gate movements
Time 10s: Gates reach new positions
Time 10.1s: Flow Monitoring confirms new state
```

### Scenario 2: Manual Gate Coordination
```
Monday 8:00 AM: Field team receives work order for Gate G025
- Target: Open from 40% to 70%
- Reason: Increase flow to Zone 2

10:30 AM: Team arrives at gate
10:35 AM: Team updates mobile app - "Starting adjustment"
10:36 AM: Flow Monitoring notified - enters "transitioning" state
10:45 AM: Team completes adjustment
10:46 AM: Mobile app update - "Completed: 68% opening"
10:47 AM: Flow Monitoring updates state
10:48 AM: Recalculates network flows
10:50 AM: Notifies Gravity Optimizer of actual vs planned
```

### Scenario 3: Auto-to-Manual Transition
```
Trigger: SCADA communication lost to Gate G001

1. SCADA Integration detects timeout (30 seconds)
2. Notifies Flow Monitoring - "G001 offline"
3. Flow Monitoring:
   - Marks G001 as "manual mode required"
   - Preserves last known state
   - Calculates impact on flows
4. Notifies Scheduled Field Ops - "Emergency work order needed"
5. Field Ops generates high-priority work order
6. Assigns to nearest available team
7. Team manually maintains gate position
8. When SCADA restored:
   - Gradual transition back to auto
   - Verify actual vs commanded position
   - Resume automated control
```

## Data Consistency Model

### State Synchronization
```
Primary State Holder: Flow Monitoring Service
- Source of truth for current hydraulic state
- All changes flow through this service
- Maintains version numbers for state changes

State Propagation:
1. State Change Event → Kafka Topic
2. Interested services subscribe
3. Services update local cache
4. Acknowledgment sent back
5. Flow Monitoring tracks sync status
```

### Conflict Resolution
```
Priority Order (highest to lowest):
1. Safety overrides (emergency stop)
2. SCADA hardware limits
3. Manual field operations in progress
4. Optimization targets
5. Historical patterns
```

## Performance Requirements

### Latency Budgets
```
Sensor → State Update: 100ms total
- Sensor → SCADA: 20ms
- SCADA → Flow Monitoring: 30ms
- State Calculation: 40ms
- Cache Update: 10ms

Optimization Cycle: 5 seconds total
- State Query: 100ms
- Optimization Algorithm: 4.5s
- Result Transmission: 200ms
- Validation: 200ms

Manual Update: 1 second total
- Mobile → API: 200ms
- API → Flow Monitoring: 300ms
- State Update: 400ms
- Confirmations: 100ms
```

## Special Considerations for Gravity Optimization

### Why Gravity Matters
In the Munbon system:
- No pumps - purely gravity-driven
- Water flows from higher to lower elevation
- Energy = elevation difference
- Optimization minimizes unnecessary drops

### Gravity Optimization Objectives
```python
minimize:
  1. Total head loss (preserve elevation)
  2. Number of gate movements (wear reduction)
  3. Deviation from farmer requests
  
subject to:
  - Minimum water levels maintained
  - Maximum velocities not exceeded
  - Fair distribution among zones
  - Time-of-delivery constraints
```

### Integration with Flow Monitoring
```
Gravity Optimizer needs from Flow Monitoring:
- Accurate water surface elevations
- Head loss through gates
- Canal friction losses
- Current flow paths

Flow Monitoring provides:
- Real-time hydraulic grade lines
- Energy dissipation calculations
- Alternative path analysis
- Elevation-based routing options
```

## Emergency Procedures

### Service Failure Cascade
```
If Gravity Optimization fails:
→ Flow Monitoring uses last good optimization
→ Falls back to historical patterns
→ Maintains current flows unless critical

If Flow Monitoring fails:
→ All gates freeze current position
→ SCADA enters local control mode
→ Field ops notified for manual takeover
→ System enters "safe mode"

If SCADA Integration fails:
→ All automated gates become manual
→ Field ops generates emergency schedule
→ Teams dispatched to critical gates
→ Manual control until restored

If Field Operations fails:
→ Flow Monitoring continues automated control
→ Manual gates remain at last position
→ Emergency contacts activated
→ Backup coordination via phone/radio
```

This integrated system ensures continuous water delivery even during partial failures, with graceful degradation and clear handoff procedures between automated and manual control.