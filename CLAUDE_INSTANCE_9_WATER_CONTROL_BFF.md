# Claude Instance 9: Water Control BFF Service

## Scope of Work
This instance handles the Backend-for-Frontend service for real-time water control operations, gate management, and emergency response.

## Assigned Components

### 1. **Water Control BFF Service** (Primary)
- **Path**: `/services/bff-water-control`
- **Port**: 4003
- **Responsibilities**:
  - Real-time gate control operations
  - Pump management and monitoring
  - Flow control and adjustments
  - Emergency response workflows
  - SCADA integration for operators
  - Live monitoring dashboards

### 2. **Real-time Components**
- **WebSocket Server**: Live data streaming
- **Command Queue**: Control command management
- **State Manager**: Current system state
- **Alert Engine**: Real-time alert processing

## Environment Setup

```bash
# Water Control BFF Service
cat > services/bff-water-control/.env.local << EOF
SERVICE_NAME=bff-water-control
PORT=4003
NODE_ENV=development

# WebSocket Configuration
WS_PORT=4103
WS_PATH=/ws
WS_HEARTBEAT_INTERVAL=30000
WS_RECONNECT_TIMEOUT=5000

# GraphQL Configuration
GRAPHQL_PATH=/graphql
GRAPHQL_SUBSCRIPTIONS=true
SUBSCRIPTION_PATH=/graphql/ws

# Internal Services
SCADA_SERVICE_URL=http://localhost:3010
WATER_CONTROL_SERVICE_URL=http://localhost:3013
IOT_GATEWAY_URL=http://localhost:3041
WATER_LEVEL_SERVICE_URL=http://localhost:3008
ALERT_SERVICE_URL=http://localhost:3032

# Control Parameters
COMMAND_TIMEOUT_MS=30000
COMMAND_RETRY_ATTEMPTS=3
EMERGENCY_OVERRIDE_ENABLED=true
CONTROL_LOOP_INTERVAL_MS=1000

# SCADA Configuration
SCADA_POLLING_INTERVAL_MS=5000
SCADA_CONNECTION_TIMEOUT=10000
OPC_UA_ENDPOINT=opc.tcp://localhost:4840

# Safety Limits
MAX_GATE_OPENING_RATE=10  # % per minute
MAX_PUMP_START_DELAY=300  # seconds
MIN_WATER_LEVEL_SAFETY=0.5  # meters
MAX_FLOW_RATE_CHANGE=20  # % per minute

# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=11
COMMAND_QUEUE=water-control-commands
STATE_CACHE_TTL=60

# Authentication
REQUIRE_OPERATOR_AUTH=true
OPERATOR_SESSION_TIMEOUT=1800000  # 30 minutes
TWO_FACTOR_REQUIRED=true
EOF
```

## GraphQL Schema

```graphql
type Query {
  # Current State
  getSystemState: SystemState!
  getGateStatus(gateId: ID!): GateStatus!
  getPumpStatus(pumpId: ID!): PumpStatus!
  getFlowRate(canalId: ID!): FlowRate!
  
  # Monitoring
  getActiveAlarms: [Alarm!]!
  getOperatorSessions: [OperatorSession!]!
  getCommandHistory(hours: Int!): [CommandLog!]!
  getSystemHealth: SystemHealth!
  
  # Predictions
  predictFlowImpact(command: ControlCommandInput!): FlowImpactPrediction!
  checkSafetyConstraints(command: ControlCommandInput!): SafetyCheck!
}

type Mutation {
  # Control Operations
  controlGate(input: GateControlInput!): GateControlResult!
  controlPump(input: PumpControlInput!): PumpControlResult!
  executeEmergencyStop(reason: String!): EmergencyStopResult!
  
  # Batch Operations
  executeBatchControl(commands: [ControlCommandInput!]!): BatchControlResult!
  applyControlScenario(scenarioId: ID!): ScenarioExecutionResult!
  
  # Manual Override
  enableManualOverride(deviceId: ID!, duration: Int!): OverrideResult!
  disableManualOverride(deviceId: ID!): OverrideResult!
  
  # Alarm Management
  acknowledgeAlarm(alarmId: ID!, notes: String): Alarm!
  silenceAlarm(alarmId: ID!, duration: Int!): Alarm!
}

type Subscription {
  # Real-time Updates
  systemStateUpdates: SystemStateUpdate!
  gateStatusUpdates(gateIds: [ID!]): GateStatusUpdate!
  pumpStatusUpdates(pumpIds: [ID!]): PumpStatusUpdate!
  flowRateUpdates(canalIds: [ID!]): FlowRateUpdate!
  
  # Alerts
  newAlarms(severity: AlarmSeverity): Alarm!
  commandExecutionStatus(commandId: ID!): CommandStatus!
  
  # Operator Activity
  operatorActions: OperatorAction!
}

# Control Types
type GateControlResult {
  commandId: ID!
  gate: Gate!
  previousPosition: Float!
  targetPosition: Float!
  estimatedTime: Int!
  status: CommandStatus!
  safetyChecks: [SafetyCheck!]!
}

type SystemState {
  timestamp: DateTime!
  gates: [GateStatus!]!
  pumps: [PumpStatus!]!
  waterLevels: [WaterLevel!]!
  flowRates: [FlowRate!]!
  activeAlarms: Int!
  operatorsOnline: Int!
}

input GateControlInput {
  gateId: ID!
  targetPosition: Float!  # 0-100%
  rampTime: Int  # seconds
  priority: ControlPriority!
  reason: String!
  bypassSafety: Boolean
}

enum ControlPriority {
  NORMAL
  HIGH
  EMERGENCY
}
```

## Real-time Control Flows

### 1. Gate Control Sequence
```javascript
async function controlGate(input, operatorId) {
  // Step 1: Validate operator permissions
  await validateOperatorPermissions(operatorId, input.gateId, 'CONTROL');
  
  // Step 2: Safety checks
  const safetyCheck = await performSafetyChecks(input);
  if (!safetyCheck.passed && !input.bypassSafety) {
    throw new SafetyViolationError(safetyCheck.violations);
  }
  
  // Step 3: Predict impact
  const impact = await predictControlImpact(input);
  
  // Step 4: Create command
  const command = await createControlCommand({
    ...input,
    operatorId,
    impact,
    timestamp: new Date()
  });
  
  // Step 5: Queue for execution
  await commandQueue.push(command);
  
  // Step 6: Monitor execution
  const execution = await monitorCommandExecution(command.id);
  
  return {
    commandId: command.id,
    status: execution.status,
    impact
  };
}
```

### 2. Emergency Response Flow
```javascript
async function handleEmergencyFloodResponse(alertData) {
  // Step 1: Assess situation
  const assessment = await assessFloodRisk(alertData);
  
  // Step 2: Calculate emergency actions
  const actions = await calculateEmergencyActions(assessment);
  
  // Step 3: Get operator confirmation (if time allows)
  let confirmation = { approved: true };
  if (assessment.severity !== 'CRITICAL') {
    confirmation = await requestOperatorConfirmation(actions, 30); // 30s timeout
  }
  
  // Step 4: Execute actions
  if (confirmation.approved) {
    const results = await executeEmergencyActions(actions);
    
    // Step 5: Monitor and adjust
    await monitorEmergencyResponse(results);
    
    // Step 6: Log everything
    await logEmergencyResponse({
      alert: alertData,
      assessment,
      actions,
      results
    });
  }
  
  return { actions, executed: confirmation.approved };
}
```

## WebSocket Real-time Streaming

```javascript
// WebSocket connection handler
wsServer.on('connection', (socket, req) => {
  const operator = authenticateWebSocket(req);
  
  // Subscribe to system state
  socket.on('subscribe:state', (params) => {
    const subscription = systemState.subscribe(state => {
      socket.send(JSON.stringify({
        type: 'state:update',
        data: filterStateByPermissions(state, operator)
      }));
    });
    
    socket.on('close', () => subscription.unsubscribe());
  });
  
  // Handle control commands
  socket.on('control:gate', async (data) => {
    try {
      const result = await controlGate(data, operator.id);
      socket.send(JSON.stringify({
        type: 'control:result',
        data: result
      }));
    } catch (error) {
      socket.send(JSON.stringify({
        type: 'control:error',
        error: error.message
      }));
    }
  });
});
```

## SCADA Integration

```javascript
class SCADAInterface {
  async readGatePosition(gateId) {
    const tag = `Gates.${gateId}.Position`;
    return await opcClient.readTag(tag);
  }
  
  async writeGateCommand(gateId, position) {
    const tag = `Gates.${gateId}.SetPoint`;
    await opcClient.writeTag(tag, position);
    
    // Verify write
    const readback = await opcClient.readTag(tag);
    if (Math.abs(readback - position) > 0.1) {
      throw new SCADAWriteError('Command verification failed');
    }
  }
  
  subscribeToAlarms() {
    return opcClient.subscribe('Alarms.*', (alarm) => {
      this.emit('alarm', alarm);
    });
  }
}
```

## Current Status
- ❌ Service structure: Not created
- ❌ WebSocket server: Not implemented
- ❌ SCADA integration: Not built
- ❌ Command queue: Not implemented
- ❌ Safety system: Not developed

## Priority Tasks
1. Create service with WebSocket support
2. Implement GraphQL subscriptions
3. Build SCADA OPC UA client
4. Create command queue system
5. Implement safety check engine
6. Build emergency response system
7. Create operator authentication
8. Implement audit logging

## Testing Commands

```bash
# Test gate control
curl -X POST http://localhost:4003/graphql \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer operator-token" \
  -d '{
    "query": "mutation { controlGate(input: { gateId: \"G001\", targetPosition: 50, priority: NORMAL, reason: \"Scheduled opening\" }) { commandId status } }"
  }'

# Subscribe to real-time updates (using wscat)
wscat -c ws://localhost:4103/ws \
  -H "Authorization: Bearer operator-token" \
  -x '{"type":"subscribe:state","params":{"gates":["G001","G002"]}}'

# Emergency stop
curl -X POST http://localhost:4003/graphql \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer operator-token" \
  -d '{
    "query": "mutation { executeEmergencyStop(reason: \"High water level detected\") { stoppedDevices } }"
  }'
```

## Safety Systems

```javascript
const safetyRules = [
  {
    name: 'MaxOpeningRate',
    check: (cmd) => cmd.rampTime >= (cmd.targetPosition / MAX_GATE_OPENING_RATE) * 60
  },
  {
    name: 'MinWaterLevel',
    check: async (cmd) => {
      const level = await getDownstreamLevel(cmd.gateId);
      return level > MIN_WATER_LEVEL_SAFETY;
    }
  },
  {
    name: 'ConflictingOperations',
    check: async (cmd) => {
      const active = await getActiveCommands(cmd.gateId);
      return active.length === 0;
    }
  }
];
```

## Notes for Development
- Implement fail-safe defaults
- Add redundant safety checks
- Log all control operations
- Support offline operation mode
- Implement watchdog timers
- Add operator presence detection
- Support control handover
- Create training/simulation mode