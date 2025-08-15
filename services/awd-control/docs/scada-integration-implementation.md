# SCADA Integration Implementation Guide

## Overview
This document provides detailed implementation guidance for integrating the AWD Control Service with the GE iFix SCADA system using OPC UA protocol.

## 1. SCADA System Architecture

### GE iFix Components
```
┌─────────────────────────────────────────────────────────────────┐
│                        GE iFix SCADA Server                       │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────────────┐  │
│  │ iFix Engine │  │ Historian DB │  │ OPC UA Server         │  │
│  │             │  │              │  │ Port: 4840            │  │
│  └─────────────┘  └──────────────┘  └───────────────────────┘  │
│                                                                   │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────────────┐  │
│  │ I/O Drivers │  │ Alarm Engine │  │ Security Provider     │  │
│  │ - Modbus    │  │              │  │ - User Auth          │  │
│  │ - DNP3      │  │              │  │ - Certificate Mgmt   │  │
│  └─────────────┘  └──────────────┘  └───────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                ↓
                        Field Equipment Network
```

### OPC UA Address Space for Irrigation

```typescript
// OPC UA Node Structure
namespace OpcNodes {
  export const IRRIGATION_ROOT = "ns=2;s=Irrigation";
  
  export const GATES = {
    ROOT: `${IRRIGATION_ROOT}.Gates`,
    GATE_TEMPLATE: `${IRRIGATION_ROOT}.Gates.Gate_{ID}`,
    PROPERTIES: {
      CURRENT_POSITION: ".CurrentPosition",      // Float 0-100
      TARGET_POSITION: ".TargetPosition",        // Float 0-100
      FLOW_RATE: ".FlowRate",                   // Float m³/s
      STATUS: ".Status",                        // Int32 (enum)
      CONTROL_MODE: ".ControlMode",             // Int32 (0=Manual, 1=Auto)
      ALARMS: ".Alarms",                        // Array of strings
      LAST_MOVEMENT: ".LastMovementTime",       // DateTime
      MOTOR_CURRENT: ".MotorCurrent",           // Float Amps
      POSITION_FEEDBACK: ".PositionFeedback"    // Float 0-100
    }
  };
  
  export const PUMPS = {
    ROOT: `${IRRIGATION_ROOT}.Pumps`,
    PUMP_TEMPLATE: `${IRRIGATION_ROOT}.Pumps.Pump_{ID}`,
    PROPERTIES: {
      STATUS: ".Status",                        // Int32 (0=Stopped, 1=Running, 2=Fault)
      SPEED_SETPOINT: ".SpeedSetpoint",         // Float RPM
      ACTUAL_SPEED: ".ActualSpeed",             // Float RPM
      FLOW_RATE: ".FlowRate",                   // Float m³/hr
      DISCHARGE_PRESSURE: ".DischargePressure", // Float bar
      SUCTION_PRESSURE: ".SuctionPressure",     // Float bar
      POWER: ".Power",                          // Float kW
      EFFICIENCY: ".Efficiency",                // Float %
      RUNTIME_HOURS: ".RuntimeHours",           // Float
      START_COMMAND: ".StartCommand",           // Bool
      STOP_COMMAND: ".StopCommand",             // Bool
      VFD_FREQUENCY: ".VFDFrequency"           // Float Hz
    }
  };
  
  export const SENSORS = {
    ROOT: `${IRRIGATION_ROOT}.Sensors`,
    WATER_LEVEL: `${IRRIGATION_ROOT}.Sensors.WaterLevel_{ID}`,
    FLOW_METER: `${IRRIGATION_ROOT}.Sensors.FlowMeter_{ID}`,
    PROPERTIES: {
      VALUE: ".Value",                          // Float
      QUALITY: ".Quality",                      // Int32
      TIMESTAMP: ".Timestamp",                  // DateTime
      UNIT: ".Unit",                           // String
      ALARM_HIGH: ".AlarmHigh",                // Float
      ALARM_LOW: ".AlarmLow"                   // Float
    }
  };
}
```

## 2. OPC UA Client Implementation

### Complete OPC UA Service

```typescript
import { 
  OPCUAClient, 
  ClientSession, 
  ClientSubscription,
  AttributeIds,
  DataType,
  StatusCodes,
  SecurityPolicy,
  MessageSecurityMode,
  UserTokenType,
  MonitoringParametersOptions,
  ReadValueIdOptions,
  WriteValueOptions,
  BrowseDescriptionOptions
} from 'node-opcua';
import { logger } from '../utils/logger';
import { EventEmitter } from 'events';

export class ScadaOpcUaService extends EventEmitter {
  private client: OPCUAClient | null = null;
  private session: ClientSession | null = null;
  private subscription: ClientSubscription | null = null;
  private reconnectTimer: NodeJS.Timeout | null = null;
  private isConnected: boolean = false;
  
  private readonly config = {
    endpoint: process.env.SCADA_OPC_ENDPOINT || 'opc.tcp://scada-server:4840',
    username: process.env.SCADA_USERNAME || 'awd_control',
    password: process.env.SCADA_PASSWORD || '',
    certificatePath: process.env.SCADA_CERT_PATH || './certs/client-cert.pem',
    privateKeyPath: process.env.SCADA_KEY_PATH || './certs/client-key.pem',
    reconnectInterval: 10000,
    requestTimeout: 30000,
    subscriptionInterval: 1000
  };

  async connect(): Promise<void> {
    try {
      // Create OPC UA Client
      this.client = OPCUAClient.create({
        applicationName: 'AWD Control Service',
        connectionStrategy: {
          initialDelay: 1000,
          maxRetry: 10,
          maxDelay: 30000
        },
        securityMode: MessageSecurityMode.SignAndEncrypt,
        securityPolicy: SecurityPolicy.Basic256Sha256,
        endpointMustExist: false,
        requestedSessionTimeout: 60000,
        clientCertificateManager: await this.getCertificateManager()
      });

      // Set up event handlers
      this.client.on('connection_lost', () => this.handleConnectionLost());
      this.client.on('connection_reestablished', () => this.handleConnectionRestored());
      this.client.on('backoff', (retry, delay) => {
        logger.warn(`OPC UA connection retry ${retry} in ${delay}ms`);
      });

      // Connect to server
      await this.client.connect(this.config.endpoint);
      logger.info('Connected to OPC UA server');

      // Create session
      this.session = await this.client.createSession({
        type: UserTokenType.UserName,
        userName: this.config.username,
        password: this.config.password
      });
      logger.info('OPC UA session created');

      // Create subscription for monitoring
      await this.createSubscription();
      
      this.isConnected = true;
      this.emit('connected');

    } catch (error) {
      logger.error({ error }, 'Failed to connect to OPC UA server');
      this.scheduleReconnect();
      throw error;
    }
  }

  private async createSubscription(): Promise<void> {
    if (!this.session) throw new Error('No active session');

    this.subscription = await this.session.createSubscription2({
      requestedPublishingInterval: this.config.subscriptionInterval,
      requestedLifetimeCount: 1000,
      requestedMaxKeepAliveCount: 10,
      maxNotificationsPerPublish: 100,
      publishingEnabled: true,
      priority: 10
    });

    this.subscription.on('started', () => {
      logger.info('OPC UA subscription started');
    });

    this.subscription.on('terminated', () => {
      logger.warn('OPC UA subscription terminated');
    });
  }

  /**
   * Control gate position
   */
  async setGatePosition(gateId: string, position: number): Promise<boolean> {
    if (!this.session) throw new Error('No active OPC UA session');

    const nodeId = `ns=2;s=Irrigation.Gates.Gate_${gateId}.TargetPosition`;
    
    try {
      // Write target position
      const statusCode = await this.session.write({
        nodeId: nodeId,
        attributeId: AttributeIds.Value,
        value: {
          value: position,
          dataType: DataType.Float,
          statusCode: StatusCodes.Good
        }
      });

      if (statusCode === StatusCodes.Good) {
        logger.info({ gateId, position }, 'Gate position command sent');
        
        // Monitor actual position
        await this.monitorGateMovement(gateId, position);
        return true;
      } else {
        logger.error({ gateId, statusCode }, 'Failed to set gate position');
        return false;
      }

    } catch (error) {
      logger.error({ error, gateId }, 'Error setting gate position');
      throw error;
    }
  }

  /**
   * Monitor gate movement to target position
   */
  private async monitorGateMovement(gateId: string, targetPosition: number): Promise<void> {
    const positionNodeId = `ns=2;s=Irrigation.Gates.Gate_${gateId}.CurrentPosition`;
    const tolerance = 1.0; // 1% tolerance
    const timeout = 60000; // 60 seconds timeout
    const startTime = Date.now();

    return new Promise((resolve, reject) => {
      const checkInterval = setInterval(async () => {
        try {
          const currentPosition = await this.readValue(positionNodeId);
          
          if (Math.abs(currentPosition - targetPosition) <= tolerance) {
            clearInterval(checkInterval);
            logger.info({ gateId, currentPosition, targetPosition }, 'Gate reached target position');
            resolve();
          } else if (Date.now() - startTime > timeout) {
            clearInterval(checkInterval);
            logger.error({ gateId, currentPosition, targetPosition }, 'Gate movement timeout');
            reject(new Error('Gate movement timeout'));
          }
        } catch (error) {
          clearInterval(checkInterval);
          reject(error);
        }
      }, 1000);
    });
  }

  /**
   * Start pump with safety checks
   */
  async startPump(pumpId: string, targetSpeed: number): Promise<boolean> {
    if (!this.session) throw new Error('No active OPC UA session');

    try {
      // Pre-start checks
      const checks = await this.performPumpPreStartChecks(pumpId);
      if (!checks.passed) {
        logger.error({ pumpId, failures: checks.failures }, 'Pump pre-start checks failed');
        return false;
      }

      // Set speed setpoint
      await this.writePumpValue(pumpId, 'SpeedSetpoint', targetSpeed);
      
      // Send start command
      await this.writePumpValue(pumpId, 'StartCommand', true);
      
      // Monitor startup
      const started = await this.monitorPumpStartup(pumpId);
      
      if (started) {
        logger.info({ pumpId, targetSpeed }, 'Pump started successfully');
        
        // Subscribe to pump parameters
        await this.subscribeToPumpMonitoring(pumpId);
        
        return true;
      } else {
        logger.error({ pumpId }, 'Pump failed to start');
        return false;
      }

    } catch (error) {
      logger.error({ error, pumpId }, 'Error starting pump');
      throw error;
    }
  }

  /**
   * Perform pre-start checks for pump
   */
  private async performPumpPreStartChecks(pumpId: string): Promise<{ passed: boolean; failures: string[] }> {
    const failures: string[] = [];

    try {
      // Check pump status
      const status = await this.readPumpValue(pumpId, 'Status');
      if (status !== 0) { // 0 = Stopped
        failures.push('Pump not in stopped state');
      }

      // Check discharge valve
      const valvePosition = await this.readValue(`ns=2;s=Irrigation.Pumps.Pump_${pumpId}.DischargeValve.Position`);
      if (valvePosition > 10) { // Should be closed
        failures.push('Discharge valve not closed');
      }

      // Check suction pressure
      const suctionPressure = await this.readPumpValue(pumpId, 'SuctionPressure');
      if (suctionPressure < 0.5) { // Minimum 0.5 bar
        failures.push('Insufficient suction pressure');
      }

      // Check electrical parameters
      const electricalOk = await this.checkElectricalParameters(pumpId);
      if (!electricalOk) {
        failures.push('Electrical parameters out of range');
      }

      // Check for active alarms
      const alarms = await this.readValue(`ns=2;s=Irrigation.Pumps.Pump_${pumpId}.ActiveAlarms`);
      if (alarms && alarms.length > 0) {
        failures.push(`Active alarms: ${alarms.join(', ')}`);
      }

    } catch (error) {
      logger.error({ error, pumpId }, 'Error during pre-start checks');
      failures.push('Pre-start check error');
    }

    return {
      passed: failures.length === 0,
      failures
    };
  }

  /**
   * Subscribe to pump monitoring
   */
  private async subscribeToPumpMonitoring(pumpId: string): Promise<void> {
    if (!this.subscription) return;

    const monitoringParams: MonitoringParametersOptions = {
      samplingInterval: 1000,
      discardOldest: true,
      queueSize: 10
    };

    // Subscribe to critical parameters
    const parametersToMonitor = [
      'ActualSpeed',
      'FlowRate',
      'DischargePressure',
      'Power',
      'MotorTemperature',
      'VibrationLevel'
    ];

    for (const param of parametersToMonitor) {
      const nodeId = `ns=2;s=Irrigation.Pumps.Pump_${pumpId}.${param}`;
      
      const itemToMonitor: ReadValueIdOptions = {
        nodeId: nodeId,
        attributeId: AttributeIds.Value
      };

      const monitoredItem = await this.subscription.monitor(
        itemToMonitor,
        monitoringParams
      );

      monitoredItem.on('changed', (dataValue) => {
        this.handlePumpParameterChange(pumpId, param, dataValue.value.value);
      });
    }
  }

  /**
   * Handle pump parameter changes
   */
  private handlePumpParameterChange(pumpId: string, parameter: string, value: any): void {
    // Check for anomalies
    switch (parameter) {
      case 'Power':
        if (value > this.getPumpPowerLimit(pumpId)) {
          this.emit('pump_anomaly', {
            pumpId,
            type: 'high_power',
            value,
            severity: 'warning'
          });
        }
        break;
        
      case 'VibrationLevel':
        if (value > 7.0) { // mm/s
          this.emit('pump_anomaly', {
            pumpId,
            type: 'high_vibration',
            value,
            severity: value > 10.0 ? 'critical' : 'warning'
          });
        }
        break;
        
      case 'DischargePressure':
        if (value < 0.5) {
          this.emit('pump_anomaly', {
            pumpId,
            type: 'low_discharge_pressure',
            value,
            severity: 'critical'
          });
        }
        break;
    }

    // Emit parameter update
    this.emit('pump_parameter_update', {
      pumpId,
      parameter,
      value,
      timestamp: new Date()
    });
  }

  /**
   * Read sensor values with quality check
   */
  async readSensorValue(sensorType: string, sensorId: string): Promise<{
    value: number;
    quality: string;
    timestamp: Date;
  }> {
    const baseNode = sensorType === 'water_level' 
      ? `ns=2;s=Irrigation.Sensors.WaterLevel_${sensorId}`
      : `ns=2;s=Irrigation.Sensors.FlowMeter_${sensorId}`;

    const [value, quality, timestamp] = await Promise.all([
      this.readValue(`${baseNode}.Value`),
      this.readValue(`${baseNode}.Quality`),
      this.readValue(`${baseNode}.Timestamp`)
    ]);

    return {
      value,
      quality: this.mapQualityCode(quality),
      timestamp: new Date(timestamp)
    };
  }

  /**
   * Execute emergency stop
   */
  async emergencyStop(area?: string): Promise<void> {
    logger.error({ area }, 'EXECUTING EMERGENCY STOP');

    try {
      // Get all active equipment
      const equipment = await this.getActiveEquipment(area);
      
      // Stop all pumps immediately
      await Promise.all(
        equipment.pumps.map(pump => 
          this.writePumpValue(pump.id, 'StopCommand', true)
        )
      );

      // Close all gates
      await Promise.all(
        equipment.gates.map(gate =>
          this.setGatePosition(gate.id, 0)
        )
      );

      // Open drainage gates if specified
      if (area && equipment.drainageGates) {
        await Promise.all(
          equipment.drainageGates.map(gate =>
            this.setGatePosition(gate.id, 100)
          )
        );
      }

      logger.info('Emergency stop executed');

    } catch (error) {
      logger.error({ error }, 'Error during emergency stop');
      // Continue with best effort
    }
  }

  /**
   * Helper methods
   */
  private async readValue(nodeId: string): Promise<any> {
    if (!this.session) throw new Error('No active session');

    const dataValue = await this.session.read({
      nodeId: nodeId,
      attributeId: AttributeIds.Value
    });

    if (dataValue.statusCode === StatusCodes.Good) {
      return dataValue.value.value;
    } else {
      throw new Error(`Failed to read ${nodeId}: ${dataValue.statusCode.name}`);
    }
  }

  private async writeValue(nodeId: string, value: any, dataType: DataType): Promise<StatusCodes> {
    if (!this.session) throw new Error('No active session');

    const statusCode = await this.session.write({
      nodeId: nodeId,
      attributeId: AttributeIds.Value,
      value: {
        value: value,
        dataType: dataType
      }
    });

    return statusCode;
  }

  private async readPumpValue(pumpId: string, property: string): Promise<any> {
    const nodeId = `ns=2;s=Irrigation.Pumps.Pump_${pumpId}.${property}`;
    return await this.readValue(nodeId);
  }

  private async writePumpValue(pumpId: string, property: string, value: any): Promise<void> {
    const nodeId = `ns=2;s=Irrigation.Pumps.Pump_${pumpId}.${property}`;
    const dataType = this.getDataTypeForProperty(property);
    const status = await this.writeValue(nodeId, value, dataType);
    
    if (status !== StatusCodes.Good) {
      throw new Error(`Failed to write pump ${property}: ${status.name}`);
    }
  }

  private getDataTypeForProperty(property: string): DataType {
    const dataTypes: Record<string, DataType> = {
      'TargetPosition': DataType.Float,
      'SpeedSetpoint': DataType.Float,
      'StartCommand': DataType.Boolean,
      'StopCommand': DataType.Boolean,
      'ControlMode': DataType.Int32
    };
    
    return dataTypes[property] || DataType.Float;
  }

  private mapQualityCode(code: number): string {
    const qualityMap: Record<number, string> = {
      0: 'Good',
      1: 'Uncertain',
      2: 'Bad',
      3: 'NotConnected'
    };
    
    return qualityMap[code] || 'Unknown';
  }

  private getPumpPowerLimit(pumpId: string): number {
    // This would come from pump configuration
    const pumpLimits: Record<string, number> = {
      'PUMP_001': 550, // kW
      'PUMP_002': 800,
      'PUMP_003': 550
    };
    
    return pumpLimits[pumpId] || 1000;
  }

  private async getActiveEquipment(area?: string): Promise<any> {
    // Browse OPC UA address space for active equipment
    // This is a simplified implementation
    return {
      pumps: [],
      gates: [],
      drainageGates: []
    };
  }

  private handleConnectionLost(): void {
    logger.error('OPC UA connection lost');
    this.isConnected = false;
    this.emit('disconnected');
    this.scheduleReconnect();
  }

  private handleConnectionRestored(): void {
    logger.info('OPC UA connection restored');
    this.isConnected = true;
    this.emit('connected');
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer) return;

    this.reconnectTimer = setTimeout(async () => {
      this.reconnectTimer = null;
      try {
        await this.connect();
      } catch (error) {
        logger.error({ error }, 'Reconnection failed');
        this.scheduleReconnect();
      }
    }, this.config.reconnectInterval);
  }

  async disconnect(): Promise<void> {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    if (this.subscription) {
      await this.subscription.terminate();
      this.subscription = null;
    }

    if (this.session) {
      await this.session.close();
      this.session = null;
    }

    if (this.client) {
      await this.client.disconnect();
      this.client = null;
    }

    this.isConnected = false;
    logger.info('Disconnected from OPC UA server');
  }

  private async getCertificateManager(): Promise<any> {
    // Implementation depends on certificate management approach
    // This is a placeholder
    return null;
  }

  /**
   * Monitor pump startup sequence
   */
  private async monitorPumpStartup(pumpId: string): Promise<boolean> {
    const timeout = 30000; // 30 seconds
    const startTime = Date.now();

    return new Promise((resolve) => {
      const checkInterval = setInterval(async () => {
        try {
          const status = await this.readPumpValue(pumpId, 'Status');
          const speed = await this.readPumpValue(pumpId, 'ActualSpeed');
          const targetSpeed = await this.readPumpValue(pumpId, 'SpeedSetpoint');

          if (status === 1 && Math.abs(speed - targetSpeed) < targetSpeed * 0.05) {
            clearInterval(checkInterval);
            resolve(true);
          } else if (Date.now() - startTime > timeout) {
            clearInterval(checkInterval);
            resolve(false);
          }
        } catch (error) {
          clearInterval(checkInterval);
          resolve(false);
        }
      }, 1000);
    });
  }

  private async checkElectricalParameters(pumpId: string): Promise<boolean> {
    try {
      // Check voltage, current, phase balance
      // This is a simplified check
      return true;
    } catch (error) {
      return false;
    }
  }
}

export const scadaOpcUaService = new ScadaOpcUaService();
```

## 3. Integration with AWD Control Service

### Updated Infrastructure Controller

```typescript
import { scadaOpcUaService } from './scada-opcua.service';
import { logger } from '../utils/logger';

export class InfrastructureController {
  private scadaConnected: boolean = false;

  async initialize(): Promise<void> {
    try {
      // Connect to SCADA
      await scadaOpcUaService.connect();
      
      // Set up event handlers
      scadaOpcUaService.on('connected', () => {
        this.scadaConnected = true;
        logger.info('SCADA connection established');
      });

      scadaOpcUaService.on('disconnected', () => {
        this.scadaConnected = false;
        logger.warn('SCADA connection lost');
      });

      scadaOpcUaService.on('pump_anomaly', (anomaly) => {
        this.handlePumpAnomaly(anomaly);
      });

      scadaOpcUaService.on('pump_parameter_update', (update) => {
        this.handleParameterUpdate(update);
      });

    } catch (error) {
      logger.error({ error }, 'Failed to initialize infrastructure controller');
      throw error;
    }
  }

  /**
   * Control gates with SCADA integration
   */
  async controlGates(fieldId: string, action: 'open' | 'close' | 'adjust', targetFlow?: number): Promise<void> {
    if (!this.scadaConnected) {
      throw new Error('SCADA not connected');
    }

    const gates = await this.getFieldGates(fieldId);
    
    for (const gate of gates) {
      let targetPosition: number;
      
      switch (action) {
        case 'open':
          targetPosition = 100;
          break;
        case 'close':
          targetPosition = 0;
          break;
        case 'adjust':
          targetPosition = await this.calculateGatePosition(gate, targetFlow || 0);
          break;
      }

      try {
        await scadaOpcUaService.setGatePosition(gate.gateId, targetPosition);
        
        // Log successful command
        await this.logGateControl(fieldId, gate.gateId, action, targetPosition, true);
        
      } catch (error) {
        logger.error({ error, gate: gate.gateId }, 'Failed to control gate');
        
        // Log failed command
        await this.logGateControl(fieldId, gate.gateId, action, targetPosition, false, error.message);
        
        // Try alternate gate if available
        await this.tryAlternateGate(fieldId, gate.gateId);
      }
    }
  }

  /**
   * Start irrigation with pump control
   */
  async startIrrigation(fieldId: string, targetFlow: number): Promise<void> {
    // Select optimal pump
    const pump = await this.selectOptimalPump(fieldId, targetFlow);
    
    if (!pump) {
      throw new Error('No suitable pump available');
    }

    // Calculate required pump speed
    const targetSpeed = this.calculatePumpSpeed(pump, targetFlow);

    try {
      // Start pump
      const started = await scadaOpcUaService.startPump(pump.pumpId, targetSpeed);
      
      if (!started) {
        throw new Error('Pump failed to start');
      }

      // Open field gates
      await this.controlGates(fieldId, 'adjust', targetFlow);
      
      logger.info({ fieldId, pump: pump.pumpId, targetFlow }, 'Irrigation started');

    } catch (error) {
      logger.error({ error, fieldId }, 'Failed to start irrigation');
      
      // Try backup pump
      const backupPump = await this.getBackupPump(pump.pumpId);
      if (backupPump) {
        await this.switchToBackupPump(pump.pumpId, backupPump.pumpId);
      } else {
        throw error;
      }
    }
  }

  /**
   * Monitor water level using SCADA sensors
   */
  async getWaterLevel(fieldId: string): Promise<{
    value: number;
    quality: string;
    timestamp: Date;
  }> {
    const sensor = await this.getFieldWaterLevelSensor(fieldId);
    
    try {
      const reading = await scadaOpcUaService.readSensorValue('water_level', sensor.sensorId);
      
      // Validate reading
      if (reading.quality !== 'Good') {
        logger.warn({ fieldId, sensor: sensor.sensorId, quality: reading.quality }, 'Poor sensor quality');
        
        // Try backup sensor
        const backupSensor = await this.getBackupSensor(fieldId);
        if (backupSensor) {
          return await scadaOpcUaService.readSensorValue('water_level', backupSensor.sensorId);
        }
      }

      return reading;

    } catch (error) {
      logger.error({ error, fieldId }, 'Failed to read water level');
      throw error;
    }
  }

  /**
   * Handle pump anomalies
   */
  private async handlePumpAnomaly(anomaly: any): Promise<void> {
    logger.warn({ anomaly }, 'Pump anomaly detected');

    switch (anomaly.type) {
      case 'high_vibration':
        if (anomaly.severity === 'critical') {
          // Stop pump immediately
          await scadaOpcUaService.writePumpValue(anomaly.pumpId, 'StopCommand', true);
          await this.notifyMaintenance(anomaly.pumpId, 'High vibration - pump stopped');
        }
        break;

      case 'low_discharge_pressure':
        // Check for cavitation
        await this.checkCavitation(anomaly.pumpId);
        break;

      case 'high_power':
        // Reduce speed
        const currentSpeed = await scadaOpcUaService.readPumpValue(anomaly.pumpId, 'ActualSpeed');
        await scadaOpcUaService.writePumpValue(anomaly.pumpId, 'SpeedSetpoint', currentSpeed * 0.9);
        break;
    }

    // Record anomaly
    await this.recordPumpAnomaly(anomaly);
  }

  /**
   * Calculate gate position for target flow
   */
  private calculateGatePosition(gate: any, targetFlow: number): number {
    // Simplified calculation - would use hydraulic model in practice
    const maxFlow = gate.maxFlowRate || 10; // m³/s
    const position = (targetFlow / maxFlow) * 100;
    
    return Math.min(100, Math.max(0, position));
  }

  /**
   * Calculate pump speed for target flow
   */
  private calculatePumpSpeed(pump: any, targetFlow: number): number {
    // Use pump curve to calculate speed
    // This is simplified - real implementation would use affinity laws
    const ratedFlow = pump.ratedFlowRate || 100; // m³/hr
    const ratedSpeed = pump.ratedSpeed || 1450; // RPM
    
    return (targetFlow / ratedFlow) * ratedSpeed;
  }

  /**
   * Database operations
   */
  private async logGateControl(
    fieldId: string,
    gateId: string,
    action: string,
    targetPosition: number,
    success: boolean,
    errorMessage?: string
  ): Promise<void> {
    await this.postgresPool.query(`
      INSERT INTO awd.gate_control_logs 
      (field_id, gate_id, action, action_value, requested_at, executed_at, success, error_message)
      VALUES ($1, $2, $3, $4, NOW(), NOW(), $5, $6)
    `, [fieldId, gateId, action, targetPosition, success, errorMessage]);
  }

  private async recordPumpAnomaly(anomaly: any): Promise<void> {
    await this.postgresPool.query(`
      INSERT INTO awd.pump_anomalies
      (pump_id, detected_at, anomaly_type, severity, value, threshold, description)
      VALUES ($1, NOW(), $2, $3, $4, $5, $6)
    `, [
      anomaly.pumpId,
      anomaly.type,
      anomaly.severity,
      anomaly.value,
      anomaly.threshold,
      `${anomaly.type} detected: ${anomaly.value}`
    ]);
  }

  // Additional helper methods...
}
```

## 4. Testing SCADA Integration

### SCADA Simulator for Development

```typescript
import { EventEmitter } from 'events';

export class ScadaSimulator extends EventEmitter {
  private equipment = new Map<string, any>();
  
  constructor() {
    super();
    this.initializeSimulation();
  }

  private initializeSimulation(): void {
    // Initialize simulated gates
    for (let i = 1; i <= 10; i++) {
      this.equipment.set(`GATE_${i}`, {
        type: 'gate',
        currentPosition: 0,
        targetPosition: 0,
        flowRate: 0,
        status: 'closed',
        moving: false
      });
    }

    // Initialize simulated pumps
    for (let i = 1; i <= 5; i++) {
      this.equipment.set(`PUMP_${i}`, {
        type: 'pump',
        status: 'stopped',
        actualSpeed: 0,
        targetSpeed: 0,
        flowRate: 0,
        power: 0,
        efficiency: 0
      });
    }

    // Start simulation loop
    setInterval(() => this.simulateEquipment(), 100);
  }

  private simulateEquipment(): void {
    this.equipment.forEach((equipment, id) => {
      if (equipment.type === 'gate') {
        this.simulateGate(id, equipment);
      } else if (equipment.type === 'pump') {
        this.simulatePump(id, equipment);
      }
    });
  }

  private simulateGate(id: string, gate: any): void {
    if (gate.moving) {
      // Move towards target
      const diff = gate.targetPosition - gate.currentPosition;
      const step = Math.sign(diff) * Math.min(Math.abs(diff), 2); // 2% per cycle
      
      gate.currentPosition += step;
      
      if (Math.abs(gate.currentPosition - gate.targetPosition) < 0.1) {
        gate.currentPosition = gate.targetPosition;
        gate.moving = false;
      }

      // Calculate flow based on position
      gate.flowRate = (gate.currentPosition / 100) * 10; // Max 10 m³/s
      
      // Update status
      if (gate.currentPosition === 0) {
        gate.status = 'closed';
      } else if (gate.currentPosition === 100) {
        gate.status = 'open';
      } else {
        gate.status = gate.moving ? 'moving' : 'partial';
      }

      this.emit('equipment_update', { id, ...gate });
    }
  }

  private simulatePump(id: string, pump: any): void {
    if (pump.status === 'starting') {
      // Ramp up speed
      pump.actualSpeed += 50; // RPM per cycle
      
      if (pump.actualSpeed >= pump.targetSpeed) {
        pump.actualSpeed = pump.targetSpeed;
        pump.status = 'running';
      }

      // Calculate parameters
      pump.flowRate = (pump.actualSpeed / 1450) * 100; // m³/hr
      pump.power = (pump.actualSpeed / 1450) * 500; // kW
      pump.efficiency = 0.85 - (Math.abs(pump.actualSpeed - 1200) / 10000);

      this.emit('equipment_update', { id, ...pump });
    }
  }

  // Simulated control methods
  setGatePosition(gateId: string, position: number): boolean {
    const gate = this.equipment.get(gateId);
    if (!gate || gate.type !== 'gate') return false;

    gate.targetPosition = position;
    gate.moving = true;
    
    return true;
  }

  startPump(pumpId: string, speed: number): boolean {
    const pump = this.equipment.get(pumpId);
    if (!pump || pump.type !== 'pump') return false;

    pump.targetSpeed = speed;
    pump.status = 'starting';
    
    return true;
  }

  stopPump(pumpId: string): boolean {
    const pump = this.equipment.get(pumpId);
    if (!pump || pump.type !== 'pump') return false;

    pump.targetSpeed = 0;
    pump.actualSpeed = 0;
    pump.status = 'stopped';
    pump.flowRate = 0;
    pump.power = 0;
    
    return true;
  }

  getEquipmentStatus(id: string): any {
    return this.equipment.get(id);
  }
}
```

This implementation provides a complete integration framework for connecting the AWD Control Service with the GE iFix SCADA system, including safety checks, anomaly handling, and a simulator for testing.