const typeDefs = `#graphql
  scalar DateTime
  scalar JSON

  type Query {
    # Gate Information
    getAutomaticGates: [AutomaticGate!]!
    getGateStatus(gateName: String!): GateStatus
    
    # Water Demand Calculations
    getWaterDemandCalculations(params: WaterDemandInput): WaterDemandResult!
    
    # Water Planning BFF Integration
    getZoneWaterDemands(zoneId: String!, weekStart: String): ZoneWaterDemands!
    getStressedAreas: [StressedArea!]!
    getCurrentWeekDemands: [SectionDemand!]!
    
    # Orchestration
    getOrchestrationStatus(operationId: String!): OrchestrationStatus
    getActiveOrchestrations: [OrchestrationStatus!]!
    
    # Command History
    getCommandHistory(limit: Int = 50): [CommandHistory!]!
    getCommandStatus(commandId: String!): CommandStatus
    
    # Service Status
    getServiceStatus: ServiceStatus!
    getSystemHealth: SystemHealth!
  }

  type Mutation {
    # Orchestrated Water Control
    orchestrateWaterControl(input: OrchestrationInput!): OrchestrationResult!
    generateGateRecommendations(zoneId: String!, options: JSON): GateRecommendations!
    
    # Automatic Gate Control
    controlAutomaticGate(input: AutomaticGateControlInput!): GateControlResult!
    controlGateSequence(input: GateSequenceInput!): [GateControlResult!]!
    
    # Manual Gate Operations
    createManualGateJobOrder(input: ManualGateJobOrderInput!): JobOrderResult!
    
    # Emergency Operations
    executeEmergencyStop(reason: String!): EmergencyStopResult!
  }

  type Subscription {
    # Real-time Updates
    gateStatusUpdates(gateNames: [String!]): GateStatusUpdate!
    commandStatusUpdates(commandId: String!): CommandStatusUpdate!
    systemAlerts: SystemAlert!
  }

  # Gate Types
  type AutomaticGate {
    alias: String!
    stationCode: String!
    levels: GateLevels!
    cumulativeLevels: CumulativeLevels!
  }

  type GateLevels {
    l1: Float!
    l2: Float!
    l3: Float!
    l4: Float!
  }

  type CumulativeLevels {
    level_1: Float!
    level_2: Float!
    level_3: Float!
    level_4: Float!
  }

  type GateStatus {
    gateName: String!
    currentLevel: Int
    currentHeight: Float
    lastCommand: CommandHistory
    isOnline: Boolean!
    lastUpdate: DateTime
  }

  # Command Types
  type GateControlResult {
    commandId: String!
    scadaCommandId: Int
    gateName: String!
    targetLevel: Int!
    gateLevel: Float!
    startDateTime: DateTime!
    status: String!
  }

  type CommandHistory {
    commandId: String!
    type: String!
    gateName: String
    targetLevel: Int
    gateLevel: Float
    startDateTime: DateTime
    createdAt: DateTime!
    status: String!
    scadaStatus: ScadaStatus
  }

  type ScadaStatus {
    id: Int!
    gateName: String!
    gateLevel: Float!
    startDateTime: DateTime!
    completed: Boolean!
    status: String!
  }

  type CommandStatus {
    commandId: String!
    type: String!
    status: String!
    scadaStatus: ScadaStatus
    createdAt: DateTime!
  }

  # Job Order Types
  type JobOrderResult {
    id: String!
    type: String!
    operatorName: String!
    executionDate: DateTime!
    gates: [ManualGateOperation!]!
    createdAt: DateTime!
    status: String!
  }

  type ManualGateOperation {
    gateName: String!
    location: String!
    zone: Int!
    currentHeight: Float!
    targetHeight: Float!
    openTime: String
    closeTime: String
    instructions: [String!]!
  }

  # Water Demand Types
  type WaterDemandResult {
    flowMonitoring: JSON
    gravityOptimization: JSON
    scheduledOperations: JSON
    recommendations: Recommendations!
  }

  type Recommendations {
    automaticGates: [AutomaticGateRecommendation!]!
    manualGates: [ManualGateRecommendation!]!
    warnings: [Warning!]!
  }

  type AutomaticGateRecommendation {
    gateName: String!
    targetLevel: Int!
    reason: String!
    priority: String!
  }

  type ManualGateRecommendation {
    gateName: String!
    targetHeight: Float!
    openTime: String
    closeTime: String
    reason: String!
  }

  type Warning {
    type: String!
    message: String!
    value: Float
    details: JSON
  }

  # System Types
  type ServiceStatus {
    flowMonitoring: String!
    gravityOptimizer: String!
    scheduledFieldOps: String!
    waterLevel: String!
    alertService: String!
  }

  type SystemHealth {
    status: String!
    uptime: Int!
    memoryUsage: Float!
    activeConnections: Int!
    lastCheck: DateTime!
  }

  type EmergencyStopResult {
    success: Boolean!
    stoppedGates: [String!]!
    message: String!
    timestamp: DateTime!
  }

  # Update Types
  type GateStatusUpdate {
    gateName: String!
    previousLevel: Int
    currentLevel: Int
    timestamp: DateTime!
  }

  type CommandStatusUpdate {
    commandId: String!
    status: String!
    progress: Float
    timestamp: DateTime!
  }

  type SystemAlert {
    id: String!
    type: String!
    severity: String!
    message: String!
    details: JSON
    timestamp: DateTime!
  }

  # Input Types
  input AutomaticGateControlInput {
    gateName: String!
    targetLevel: Int!
    startDateTime: DateTime
    reason: String!
  }

  input GateSequenceInput {
    gateName: String!
    fromLevel: Int!
    toLevel: Int!
    startDateTime: DateTime
    intervalMinutes: Int = 5
  }

  input ManualGateJobOrderInput {
    gates: [ManualGateInput!]!
    operatorName: String!
    executionDate: DateTime
  }

  input ManualGateInput {
    gateName: String!
    location: String!
    zone: Int!
    currentHeight: Float = 0
    targetHeight: Float!
    openTime: String
    closeTime: String
  }

  input WaterDemandInput {
    zone: Int
    startDate: DateTime
    endDate: DateTime
    includeScheduled: Boolean = true
  }

  # Water Planning BFF Integration Types
  type ZoneWaterDemands {
    zone_id: String!
    week_start_date: String!
    total_adjusted_demand_m3: Float!
    sections: [SectionWaterDemand!]!
    calculation_method: String!
    calculation_timestamp: DateTime!
  }

  type SectionWaterDemand {
    area_id: String!
    area_type: String!
    base_demand_m3: Float!
    adjusted_demand_m3: Float!
    sensor_adjustment_factor: Float
    calculation_method: String!
    stress_indicator: Float
    delivery_efficiency_pct: Float
  }

  type SectionDemand {
    area_id: String!
    area_type: String!
    week_start_date: String!
    adjusted_demand_m3: Float!
    sensor_adjustment_factor: Float
    stress_indicator: Float
  }

  type StressedArea {
    area_id: String!
    zone_id: String!
    stress_level: Float!
    deficit_m3: Float!
    priority: Int!
    last_delivery: DateTime
  }

  # Orchestration Types
  type OrchestrationStatus {
    operation_id: String!
    zone_id: String!
    status: String!
    started_at: DateTime!
    completed_at: DateTime
    error: String
    results: OrchestrationResults
  }

  type OrchestrationResults {
    automatic_gates: [GateControlResult!]!
    manual_gates: [JobOrderResult!]!
    summary: OrchestrationSummary!
  }

  type OrchestrationSummary {
    total_commands: Int!
    successful: Int!
    failed: Int!
  }

  type OrchestrationResult {
    operation_id: String!
    zone_id: String!
    demands_summary: DemandsSummary!
    gate_settings: OptimizedGateSettings!
    control_sequence: ControlSequence!
    execution_results: OrchestrationResults!
    validation: ValidationResult!
    monitoring_enabled: Boolean!
  }

  type DemandsSummary {
    zone_id: String!
    total_demand_m3: Float!
    total_flow_m3s: Float!
    section_count: Int!
    high_priority_count: Int!
    calculation_timestamp: DateTime!
  }

  type OptimizedGateSettings {
    individual_settings: [GateSetting!]!
    operation_groups: [OperationGroup!]!
    total_gates: Int!
    total_flow: Float!
  }

  type GateSetting {
    gate_name: String!
    required_flow_m3s: Float!
    required_opening_cm: Float!
    selected_level: Int!
    selected_opening_cm: Float!
    actual_flow_m3s: Float!
    flow_difference_pct: String!
    capacity_utilization_pct: String!
  }

  type OperationGroup {
    gates: [GateSetting!]!
    type: String!
    total_flow: Float!
  }

  type ControlSequence {
    sequence: [ControlOperation!]!
    total_duration_minutes: Float!
    operation_count: Int!
    group_count: Int!
  }

  type ControlOperation {
    sequence: Int!
    gate_name: String!
    target_level: Int!
    target_opening_cm: Float!
    expected_flow_m3s: Float!
    scheduled_time: DateTime!
    group_id: Int!
    priority: Int!
    metadata: JSON
  }

  type ValidationResult {
    valid: Boolean!
    warnings: [ValidationIssue!]!
    errors: [ValidationIssue!]!
  }

  type ValidationIssue {
    gate: String
    issue: String!
    value: String
    required: String
    available: String
  }

  type GateRecommendations {
    recommendations: [GateRecommendation!]!
    summary: DemandsSummary!
    stressed_areas: [StressedArea!]!
  }

  type GateRecommendation {
    section_id: String!
    zone_id: String!
    weekly_demand_m3: Float!
    required_flow_m3s: Float!
    required_flow_lps: Float!
    priority: Int!
    calculation_method: String!
    sensor_adjustment: Float
    stress_level: Float
    metadata: JSON
  }

  # Input Types for Orchestration
  input OrchestrationInput {
    zoneId: String!
    options: OrchestrationOptions
  }

  input OrchestrationOptions {
    operationDelay: Int
    enableRollback: Boolean
    priorityThreshold: Int
  }
`;

module.exports = typeDefs;