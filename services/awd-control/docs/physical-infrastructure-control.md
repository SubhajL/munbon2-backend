# Physical Infrastructure Control - AWD Control Service

## Overview
The AWD Control Service manages physical irrigation infrastructure including gates, pumps, and water distribution systems. Currently, the service has placeholder implementations for SCADA integration, as the actual SCADA system integration is pending.

## Architecture

### Control Flow
```
AWD Control Service
    ↓
Kafka Message Bus
    ↓
SCADA Integration Service (Planned)
    ↓
GE iFix OPC UA Server
    ↓
Physical Infrastructure (Gates/Pumps)
```

## 1. Gate Control System

### Gate Identification
Each field has one or more irrigation gates identified by unique IDs:
```typescript
// Current implementation (placeholder)
private async getFieldGates(fieldId: string): Promise<Array<{ gateId: string }>> {
  return [{ gateId: `GATE_${fieldId}_1` }]; // Placeholder
}

// Future implementation with database
private async getFieldGates(fieldId: string): Promise<GateConfiguration[]> {
  const result = await this.postgresPool.query(`
    SELECT 
      g.gate_id,
      g.gate_type,
      g.location_coordinates,
      g.max_flow_rate_cms,
      g.current_position_percent,
      g.operational_status,
      g.last_maintenance_date,
      gc.canal_id,
      gc.canal_section
    FROM awd.field_gates fg
    JOIN awd.gates g ON fg.gate_id = g.id
    JOIN awd.gate_canal gc ON g.id = gc.gate_id
    WHERE fg.field_id = $1
      AND g.operational_status = 'active'
    ORDER BY fg.priority
  `, [fieldId]);
  
  return result.rows;
}
```

### Gate Control Commands

#### Basic Operations
```typescript
interface GateCommand {
  gateId: string;
  action: 'open' | 'close' | 'adjust' | 'emergency_close';
  targetPosition?: number; // 0-100% for adjust
  rampTime?: number; // seconds to reach target position
  priority: 'normal' | 'high' | 'emergency';
}
```

#### Command Execution Process
1. **Command Generation**
   ```typescript
   async controlGates(fieldId: string, action: 'open' | 'close' | 'adjust'): Promise<void> {
     // Get all gates for the field
     const gates = await this.getFieldGates(fieldId);
     
     // Calculate opening percentage based on required flow
     const openingPercent = await this.calculateGateOpening(fieldId, targetFlowRate);
     
     // Send commands to each gate
     for (const gate of gates) {
       const command: GateCommand = {
         gateId: gate.gateId,
         action: action,
         targetPosition: openingPercent,
         rampTime: 60, // 1 minute ramp time
         priority: 'normal'
       };
       
       await this.sendGateCommand(command);
     }
   }
   ```

2. **Command Transmission via Kafka**
   ```typescript
   await publishMessage(KafkaTopics.GATE_CONTROL_COMMANDS, {
     commandId: uuidv4(),
     fieldId,
     gates: gates.map(g => ({
       gateId: g.gateId,
       targetPosition: g.targetPosition,
       expectedFlowRate: g.expectedFlowRate
     })),
     action,
     priority: command.priority,
     timestamp: new Date().toISOString(),
     expectedExecutionTime: 60, // seconds
     callbackTopic: KafkaTopics.GATE_STATUS_UPDATES
   });
   ```

3. **SCADA Integration (Future Implementation)**
   ```typescript
   // SCADA Integration Service will:
   class ScadaGateController {
     async executeGateCommand(command: GateCommand): Promise<GateResponse> {
       // Connect to OPC UA server
       const opcClient = await this.connectToOpcServer();
       
       // Map gate ID to OPC UA node
       const nodeId = this.getOpcNodeId(command.gateId);
       
       // Write command to OPC UA
       const result = await opcClient.writeValue({
         nodeId: nodeId,
         attributeId: AttributeIds.Value,
         value: {
           value: command.targetPosition,
           dataType: DataType.Float
         }
       });
       
       // Monitor feedback
       const status = await this.monitorGateStatus(command.gateId);
       
       return {
         success: status.currentPosition === command.targetPosition,
         actualPosition: status.currentPosition,
         flowRate: status.measuredFlowRate,
         executionTime: status.transitionTime
       };
     }
   }
   ```

### Gate Status Monitoring
```typescript
interface GateStatus {
  gateId: string;
  currentPosition: number; // 0-100%
  targetPosition: number;
  actualFlowRate: number; // m³/s
  motorCurrent: number; // Amps
  vibration: number; // mm/s
  temperature: number; // °C
  lastMovementTime: Date;
  alarms: string[];
  operationalStatus: 'open' | 'closed' | 'opening' | 'closing' | 'fault' | 'maintenance';
}

// Continuous monitoring
async monitorGateStatus(gateId: string): Promise<void> {
  const subscription = setInterval(async () => {
    const status = await this.getGateStatus(gateId);
    
    // Check for anomalies
    if (status.motorCurrent > MOTOR_CURRENT_THRESHOLD) {
      await this.handleGateAnomaly(gateId, 'high_motor_current', status);
    }
    
    // Update database
    await this.updateGateStatus(gateId, status);
    
    // Publish status update
    await publishMessage(KafkaTopics.GATE_STATUS_UPDATES, status);
  }, 5000); // Check every 5 seconds
}
```

## 2. Pump Control System

### Pump Types and Configuration
```typescript
interface PumpConfiguration {
  pumpId: string;
  pumpType: 'centrifugal' | 'submersible' | 'turbine';
  ratedPowerKw: number;
  ratedFlowRate: number; // m³/hr
  ratedHead: number; // meters
  efficiencyCurve: EfficiencyCurve;
  location: GeoPoint;
  servingFields: string[]; // field IDs
  variableSpeedDrive: boolean;
}
```

### Pump Control Operations

#### Starting Sequence
```typescript
async startPump(pumpId: string, targetFlowRate: number): Promise<PumpStartResult> {
  // Pre-start checks
  const checks = await this.performPreStartChecks(pumpId);
  if (!checks.passed) {
    throw new Error(`Pre-start checks failed: ${checks.failures.join(', ')}`);
  }
  
  // Calculate optimal speed for target flow
  const targetSpeed = await this.calculateOptimalSpeed(pumpId, targetFlowRate);
  
  // Start sequence
  const startSequence = [
    { step: 'close_discharge_valve', duration: 5 },
    { step: 'start_motor', duration: 10 },
    { step: 'ramp_to_speed', targetSpeed, duration: 30 },
    { step: 'open_discharge_valve', duration: 20 },
    { step: 'stabilize_flow', duration: 15 }
  ];
  
  for (const step of startSequence) {
    await this.executePumpStep(pumpId, step);
    await this.delay(step.duration * 1000);
    
    // Check for faults
    const status = await this.getPumpStatus(pumpId);
    if (status.faults.length > 0) {
      await this.emergencyStopPump(pumpId);
      throw new Error(`Pump fault during ${step.step}: ${status.faults.join(', ')}`);
    }
  }
  
  return {
    success: true,
    actualFlowRate: await this.getMeasuredFlowRate(pumpId),
    powerConsumption: await this.getPowerConsumption(pumpId),
    efficiency: await this.calculateEfficiency(pumpId)
  };
}
```

#### Variable Speed Control
```typescript
async adjustPumpSpeed(pumpId: string, newFlowRate: number): Promise<void> {
  const pump = await this.getPumpConfig(pumpId);
  
  if (!pump.variableSpeedDrive) {
    throw new Error('Pump does not have variable speed drive');
  }
  
  // Calculate new speed based on affinity laws
  const currentSpeed = await this.getCurrentSpeed(pumpId);
  const currentFlow = await this.getCurrentFlowRate(pumpId);
  const newSpeed = currentSpeed * (newFlowRate / currentFlow);
  
  // Apply constraints
  const constrainedSpeed = Math.max(
    pump.minSpeed,
    Math.min(pump.maxSpeed, newSpeed)
  );
  
  // Send speed command
  await this.sendSpeedCommand(pumpId, constrainedSpeed);
  
  // Monitor response
  await this.monitorSpeedChange(pumpId, constrainedSpeed);
}
```

### Pump Protection and Monitoring
```typescript
interface PumpProtection {
  // Electrical protection
  overCurrentLimit: number;
  underCurrentLimit: number;
  voltageImbalanceLimit: number;
  
  // Mechanical protection
  vibrationLimit: number;
  bearingTemperatureLimit: number;
  sealPressureLimit: number;
  
  // Hydraulic protection
  minFlowRate: number;
  maxFlowRate: number;
  cavitationDetection: boolean;
  dryRunProtection: boolean;
}

async monitorPumpHealth(pumpId: string): Promise<void> {
  const monitoring = setInterval(async () => {
    const data = await this.getPumpTelemetry(pumpId);
    
    // Check protection limits
    const violations = this.checkProtectionLimits(data);
    
    if (violations.critical.length > 0) {
      await this.emergencyStopPump(pumpId);
      await this.sendCriticalAlert(pumpId, violations.critical);
    } else if (violations.warnings.length > 0) {
      await this.adjustPumpOperation(pumpId, violations.warnings);
      await this.sendWarningAlert(pumpId, violations.warnings);
    }
    
    // Update performance metrics
    await this.updatePumpMetrics(pumpId, data);
  }, 1000); // Check every second for pumps
}
```

## 3. Water Distribution Coordination

### Multi-Field Coordination
```typescript
class WaterDistributionCoordinator {
  private activeIrrigations: Map<string, IrrigationSession> = new Map();
  private canalCapacities: Map<string, number> = new Map();
  
  async requestIrrigation(fieldId: string, requiredFlow: number): Promise<IrrigationAllocation> {
    // Check canal capacity
    const canal = await this.getFieldCanal(fieldId);
    const availableCapacity = await this.getAvailableCapacity(canal.id);
    
    if (requiredFlow > availableCapacity) {
      // Try to optimize existing allocations
      const optimized = await this.optimizeAllocations(canal.id, requiredFlow);
      
      if (!optimized.success) {
        // Queue the request
        return await this.queueIrrigationRequest(fieldId, requiredFlow);
      }
    }
    
    // Allocate water
    const allocation = await this.allocateWater(fieldId, requiredFlow, canal.id);
    
    // Configure infrastructure
    await this.configureInfrastructure(allocation);
    
    return allocation;
  }
  
  private async configureInfrastructure(allocation: IrrigationAllocation): Promise<void> {
    // 1. Configure main canal gates
    for (const gate of allocation.mainCanalGates) {
      await this.setGatePosition(gate.gateId, gate.position);
    }
    
    // 2. Configure distribution gates
    for (const gate of allocation.distributionGates) {
      await this.setGatePosition(gate.gateId, gate.position);
    }
    
    // 3. Start pumps if needed
    for (const pump of allocation.pumps) {
      await this.startPump(pump.pumpId, pump.flowRate);
    }
    
    // 4. Configure field gates
    for (const gate of allocation.fieldGates) {
      await this.setGatePosition(gate.gateId, gate.position);
    }
  }
}
```

### Flow Balancing Algorithm
```typescript
async balanceFlows(canalId: string): Promise<FlowBalance> {
  const sections = await this.getCanalSections(canalId);
  const demands = await this.getActiveDemands(canalId);
  
  // Build hydraulic model
  const model = new HydraulicModel(sections);
  
  // Add demands
  demands.forEach(demand => {
    model.addDemand(demand.location, demand.flowRate);
  });
  
  // Solve for gate positions
  const solution = model.solve({
    objective: 'minimize_losses',
    constraints: {
      minPressure: 0.5, // meters
      maxVelocity: 2.0, // m/s
      maintainLevels: true
    }
  });
  
  // Apply solution
  for (const [gateId, position of solution.gatePositions) {
    await this.setGatePosition(gateId, position);
  }
  
  return {
    totalFlow: solution.totalFlow,
    losses: solution.losses,
    efficiency: solution.efficiency
  };
}
```

## 4. Emergency Control Systems

### Emergency Shutdown
```typescript
async emergencyShutdown(reason: string, affectedArea?: string): Promise<void> {
  logger.error({ reason, affectedArea }, 'EMERGENCY SHUTDOWN INITIATED');
  
  // 1. Stop all pumps immediately
  const pumps = await this.getAllActivePumps(affectedArea);
  await Promise.all(pumps.map(pump => 
    this.emergencyStopPump(pump.pumpId)
  ));
  
  // 2. Close all field gates
  const fieldGates = await this.getAllOpenFieldGates(affectedArea);
  await Promise.all(fieldGates.map(gate =>
    this.emergencyCloseGate(gate.gateId)
  ));
  
  // 3. Open drainage gates if flooding risk
  if (reason.includes('flood')) {
    const drainageGates = await this.getDrainageGates(affectedArea);
    await Promise.all(drainageGates.map(gate =>
      this.openDrainageGate(gate.gateId)
    ));
  }
  
  // 4. Send alerts
  await this.sendEmergencyAlerts({
    reason,
    affectedArea,
    actions: ['pumps_stopped', 'gates_closed', 'drainage_opened'],
    timestamp: new Date()
  });
}
```

### Fault Recovery
```typescript
async handleInfrastructureFault(fault: InfrastructureFault): Promise<void> {
  switch (fault.type) {
    case 'gate_stuck':
      // Try alternate gate
      const alternate = await this.findAlternateGate(fault.gateId);
      if (alternate) {
        await this.switchToAlternateGate(fault.gateId, alternate.gateId);
      } else {
        await this.isolateSection(fault.gateId);
      }
      break;
      
    case 'pump_failure':
      // Switch to backup pump
      const backup = await this.getBackupPump(fault.pumpId);
      if (backup) {
        await this.switchToBackupPump(fault.pumpId, backup.pumpId);
      } else {
        await this.redistributeFlow(fault.pumpId);
      }
      break;
      
    case 'power_loss':
      // Switch to diesel generators
      await this.startEmergencyGenerators(fault.affectedArea);
      await this.restartCriticalSystems();
      break;
  }
}
```

## 5. Integration Points

### SCADA Communication Protocol
```typescript
interface ScadaMessage {
  messageId: string;
  timestamp: Date;
  source: 'awd_control' | 'scada_system';
  messageType: 'command' | 'status' | 'alarm' | 'acknowledgment';
  payload: {
    deviceType: 'gate' | 'pump' | 'sensor';
    deviceId: string;
    operation?: string;
    parameters?: Record<string, any>;
    status?: Record<string, any>;
  };
  priority: 'low' | 'normal' | 'high' | 'emergency';
  requiresAck: boolean;
}
```

### OPC UA Integration (Planned)
```typescript
class OpcUaClient {
  private client: OPCUAClient;
  private session: ClientSession;
  
  async connect(): Promise<void> {
    this.client = OPCUAClient.create({
      endpoint_must_exist: false,
      connectionStrategy: {
        maxRetry: 10,
        initialDelay: 2000,
        maxDelay: 10000
      }
    });
    
    await this.client.connect('opc.tcp://scada-server:4840');
    this.session = await this.client.createSession();
  }
  
  async writeGatePosition(gateId: string, position: number): Promise<void> {
    const nodeId = `ns=2;s=Gates.${gateId}.TargetPosition`;
    
    await this.session.write({
      nodeId: nodeId,
      attributeId: AttributeIds.Value,
      value: {
        value: {
          dataType: DataType.Float,
          value: position
        }
      }
    });
  }
  
  async readPumpStatus(pumpId: string): Promise<PumpStatus> {
    const nodesToRead = [
      `ns=2;s=Pumps.${pumpId}.Status`,
      `ns=2;s=Pumps.${pumpId}.Speed`,
      `ns=2;s=Pumps.${pumpId}.FlowRate`,
      `ns=2;s=Pumps.${pumpId}.Power`,
      `ns=2;s=Pumps.${pumpId}.Efficiency`
    ];
    
    const results = await this.session.read(nodesToRead);
    
    return {
      status: results[0].value.value,
      speed: results[1].value.value,
      flowRate: results[2].value.value,
      power: results[3].value.value,
      efficiency: results[4].value.value
    };
  }
}
```

## 6. Current Limitations and Future Enhancements

### Current State
- Gate control: Placeholder implementation with logging only
- Pump control: Not yet implemented
- SCADA integration: Planned but not connected
- Physical feedback: Simulated only

### Planned Enhancements
1. **Full SCADA Integration**
   - OPC UA client implementation
   - Real-time telemetry ingestion
   - Bi-directional control and monitoring

2. **Advanced Control Algorithms**
   - Model Predictive Control (MPC) for optimization
   - Machine learning for fault prediction
   - Hydraulic modeling integration

3. **Enhanced Safety Systems**
   - Redundant communication paths
   - Fail-safe positions for all equipment
   - Automatic fault isolation

4. **Performance Optimization**
   - Energy optimization algorithms
   - Wear leveling for equipment
   - Predictive maintenance scheduling

## 7. Testing Infrastructure Control

### Simulation Mode
```typescript
// Enable simulation for testing without physical hardware
export class SimulatedInfrastructure {
  private gates: Map<string, SimulatedGate> = new Map();
  private pumps: Map<string, SimulatedPump> = new Map();
  
  async simulateGateMovement(gateId: string, targetPosition: number): Promise<void> {
    const gate = this.gates.get(gateId) || new SimulatedGate(gateId);
    
    // Simulate movement time
    const moveTime = Math.abs(targetPosition - gate.currentPosition) * 1000; // 1s per %
    
    // Simulate movement
    const steps = 10;
    for (let i = 0; i <= steps; i++) {
      gate.currentPosition = gate.currentPosition + 
        (targetPosition - gate.currentPosition) * (i / steps);
      
      // Simulate flow calculation
      gate.flowRate = this.calculateGateFlow(gate.currentPosition);
      
      await this.delay(moveTime / steps);
      
      // Publish status update
      await this.publishGateStatus(gate);
    }
  }
}
```

This infrastructure control system provides the foundation for automated irrigation management, though full implementation requires integration with the actual SCADA systems and physical hardware deployed in the field.