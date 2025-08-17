# Claude Instance 17: Batch Scheduler and Field Operations

## Context
You are implementing Tasks 60 and 61 for the Munbon Irrigation Backend project. These tasks create the weekly scheduling system and field team mobile app that coordinates manual operations with automated control.

## Your Task Sequence

### Task 60: Weekly Batch Scheduler with Real-time Adaptation

**Core Responsibilities:**
1. **Demand Aggregation**
   - Collect section-level water needs from ROS/GIS
   - Group by delivery paths and time windows
   - Apply weather-based adjustments

2. **Schedule Optimization**
   - Balance competing demands with capacity constraints
   - Minimize field team travel (1-2 days/week)
   - Coordinate manual and automated gate operations
   - Respect gravity flow constraints

3. **Real-time Adaptation**
   - Monitor automated gate feedback
   - Adjust schedule based on actual flows
   - Handle weather contingencies
   - Update future operations based on current state

**Technical Specs:**
- Python/FastAPI service on port 3021
- PostgreSQL for schedule storage
- Redis for real-time state
- Integration with Flow Monitoring Service

### Task 61: Field Operations Mobile App

**Core Features:**
1. **Offline-First Architecture**
   - Download weekly schedules
   - Cache gate locations and instructions
   - Queue operations for sync when connected

2. **Gate Operation Interface**
   - GPS navigation to gates
   - Visual instructions with physical markings
   - Photo capture for gate positions
   - Digital forms for readings

3. **Real-time Sync**
   - Update central system with manual gate states
   - Receive automated gate status
   - Get push notifications for changes
   - Team communication features

**Technical Specs:**
- React Native (Android focus)
- SQLite for offline storage
- Background sync service
- Camera integration

## Key Workflows

### Weekly Planning (Monday)
1. Aggregate demands → Optimize schedule → Generate instructions
2. Push to field team devices
3. Confirm team availability

### Field Execution (Tuesday/Thursday)
1. Teams follow GPS routes
2. Set gates per instructions
3. Record actual settings
4. Sync when connected

### Real-time Adjustments
1. Monitor automated gates
2. Detect deviations
3. Update manual instructions
4. Notify field teams

## Integration Requirements
- Flow Monitoring Service (gate calculations)
- ROS/GIS Services (demands)
- Weather API (forecasts)
- SMS gateway (notifications)

## Critical Success Factors
1. Simple, clear field instructions
2. Robust offline operation
3. Accurate GPS navigation
4. Fast sync when connected
5. Battery-efficient app

## Deliverables
1. Schedule optimization engine
2. Field instruction generator
3. Mobile app with offline sync
4. Real-time adaptation algorithms
5. Team coordination features

Remember: Field teams may have limited technical skills and poor connectivity. Design for simplicity and reliability.