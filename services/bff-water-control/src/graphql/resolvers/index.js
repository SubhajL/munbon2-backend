const GateControlService = require('../../services/gate-control.service');
const IntegrationService = require('../../services/integration.service');
const WaterControlOrchestratorService = require('../../services/water-control-orchestrator.service');
const { getRecentCommands } = require('../../config/database');
const { PubSub } = require('graphql-subscriptions');

// Initialize services
const gateControlService = new GateControlService();
const integrationService = new IntegrationService();
const orchestratorService = new WaterControlOrchestratorService();
const pubsub = new PubSub();

// Subscription topics
const GATE_STATUS_UPDATE = 'GATE_STATUS_UPDATE';
const COMMAND_STATUS_UPDATE = 'COMMAND_STATUS_UPDATE';
const SYSTEM_ALERT = 'SYSTEM_ALERT';

const resolvers = {
  Query: {
    // Gate Information
    getAutomaticGates: () => {
      return gateControlService.getAutomaticGates();
    },

    getGateStatus: async (_, { gateName }) => {
      // This would integrate with SCADA in production
      // For now, return mock data
      const lastCommand = gateControlService.getCommandHistory(1)
        .find(cmd => cmd.gateName === gateName);
      
      return {
        gateName,
        currentLevel: lastCommand?.targetLevel || 0,
        currentHeight: lastCommand?.gateLevel || 0,
        lastCommand,
        isOnline: true,
        lastUpdate: new Date()
      };
    },

    // Water Demand Calculations
    getWaterDemandCalculations: async (_, { params }) => {
      return await integrationService.getWaterDemandCalculations(params || {});
    },

    // Water Demand from Planning BFF
    getZoneWaterDemands: async (_, { zoneId, weekStart }) => {
      return await orchestratorService.demandService.getZoneDemands(zoneId, weekStart);
    },

    getStressedAreas: async () => {
      return await orchestratorService.demandService.getStressedAreas();
    },

    getCurrentWeekDemands: async () => {
      return await orchestratorService.demandService.getCurrentWeekAllSections();
    },

    // Orchestration Status
    getOrchestrationStatus: (_, { operationId }) => {
      return orchestratorService.getOperationStatus(operationId);
    },

    getActiveOrchestrations: () => {
      return orchestratorService.getActiveOperations();
    },

    // Command History
    getCommandHistory: async (_, { limit }) => {
      return gateControlService.getCommandHistory(limit);
    },

    getCommandStatus: async (_, { commandId }) => {
      return await gateControlService.checkStatus(commandId);
    },

    // Service Status
    getServiceStatus: async () => {
      return await integrationService.testConnectivity();
    },

    getSystemHealth: () => {
      const uptime = process.uptime();
      const memoryUsage = process.memoryUsage();
      
      return {
        status: 'healthy',
        uptime: Math.floor(uptime),
        memoryUsage: (memoryUsage.heapUsed / memoryUsage.heapTotal) * 100,
        activeConnections: 0, // Would track WebSocket connections
        lastCheck: new Date()
      };
    }
  },

  Mutation: {
    // Orchestrated Water Control
    orchestrateWaterControl: async (_, { input }) => {
      const { zoneId, options } = input;
      
      try {
        const result = await orchestratorService.orchestrateWaterControl(zoneId, options);
        
        // Publish updates
        pubsub.publish(SYSTEM_ALERT, {
          systemAlerts: {
            id: result.operation_id,
            type: 'orchestration_started',
            severity: 'info',
            message: `Water control orchestration started for zone ${zoneId}`,
            details: { 
              operation_id: result.operation_id,
              total_gates: result.gate_settings.total_gates,
              total_flow: result.control_sequence.total_flow 
            },
            timestamp: new Date()
          }
        });
        
        return result;
      } catch (error) {
        throw new Error(`Orchestration failed: ${error.message}`);
      }
    },

    generateGateRecommendations: async (_, { zoneId, options }) => {
      return await orchestratorService.demandService.generateGateRecommendations(zoneId, options);
    },

    // Automatic Gate Control
    controlAutomaticGate: async (_, { input }) => {
      const result = await gateControlService.controlAutomaticGate(input);
      
      // Publish update
      pubsub.publish(GATE_STATUS_UPDATE, {
        gateStatusUpdates: {
          gateName: input.gateName,
          previousLevel: 0, // Would get from current status
          currentLevel: input.targetLevel,
          timestamp: new Date()
        }
      });

      pubsub.publish(COMMAND_STATUS_UPDATE, {
        commandStatusUpdates: {
          commandId: result.commandId,
          status: result.status,
          progress: 0,
          timestamp: new Date()
        }
      });

      return result;
    },

    controlGateSequence: async (_, { input }) => {
      const results = await gateControlService.controlGateSequence(input);
      
      // Publish updates for each command
      results.forEach(result => {
        pubsub.publish(COMMAND_STATUS_UPDATE, {
          commandStatusUpdates: {
            commandId: result.commandId,
            status: result.status,
            progress: 0,
            timestamp: new Date()
          }
        });
      });

      return results;
    },

    // Manual Gate Operations
    createManualGateJobOrder: async (_, { input }) => {
      const result = gateControlService.generateManualGateJobOrder(input);
      
      // Send alert about new job order
      pubsub.publish(SYSTEM_ALERT, {
        systemAlerts: {
          id: result.id,
          type: 'job_order_created',
          severity: 'info',
          message: `New job order created for ${input.operatorName}`,
          details: { jobOrderId: result.id, gateCount: input.gates.length },
          timestamp: new Date()
        }
      });

      return result;
    },

    // Emergency Operations
    executeEmergencyStop: async (_, { reason }) => {
      // Get all automatic gates
      const automaticGates = gateControlService.getAutomaticGates();
      const stoppedGates = [];

      // Send Level 1 command to all gates (closed position)
      for (const gate of automaticGates) {
        try {
          await gateControlService.controlAutomaticGate({
            gateName: gate.alias,
            targetLevel: 1,
            startDateTime: new Date(),
            reason: `EMERGENCY STOP: ${reason}`
          });
          stoppedGates.push(gate.alias);
        } catch (error) {
          console.error(`Failed to stop gate ${gate.alias}:`, error);
        }
      }

      // Send emergency alert
      pubsub.publish(SYSTEM_ALERT, {
        systemAlerts: {
          id: `emergency-${Date.now()}`,
          type: 'emergency_stop',
          severity: 'critical',
          message: `Emergency stop executed: ${reason}`,
          details: { stoppedGates, reason },
          timestamp: new Date()
        }
      });

      return {
        success: true,
        stoppedGates,
        message: `Emergency stop executed for ${stoppedGates.length} gates`,
        timestamp: new Date()
      };
    }
  },

  Subscription: {
    gateStatusUpdates: {
      subscribe: (_, { gateNames }) => {
        // Filter by gate names if provided
        if (gateNames && gateNames.length > 0) {
          return pubsub.asyncIterator([GATE_STATUS_UPDATE]);
          // Would filter in the resolve function
        }
        return pubsub.asyncIterator([GATE_STATUS_UPDATE]);
      }
    },

    commandStatusUpdates: {
      subscribe: (_, { commandId }) => {
        return pubsub.asyncIterator([COMMAND_STATUS_UPDATE]);
        // Would filter by commandId in the resolve function
      }
    },

    systemAlerts: {
      subscribe: () => pubsub.asyncIterator([SYSTEM_ALERT])
    }
  },

  // Custom scalar resolvers
  DateTime: {
    serialize: (value) => value instanceof Date ? value.toISOString() : value,
    parseValue: (value) => new Date(value),
    parseLiteral: (ast) => ast.value ? new Date(ast.value) : null
  },

  JSON: {
    serialize: (value) => value,
    parseValue: (value) => value,
    parseLiteral: (ast) => ast.value
  }
};

// Background job to check command status
setInterval(async () => {
  try {
    // Get recent SCADA commands and check their status
    const recentCommands = await getRecentCommands(1); // Last hour
    
    for (const cmd of recentCommands) {
      if (!cmd.completed) {
        // Check if enough time has passed
        const elapsed = Date.now() - new Date(cmd.startDateTime).getTime();
        if (elapsed > 60000) { // 1 minute
          // Publish status update
          pubsub.publish(COMMAND_STATUS_UPDATE, {
            commandStatusUpdates: {
              commandId: cmd.id.toString(),
              status: 'checking',
              progress: 50,
              timestamp: new Date()
            }
          });
        }
      }
    }
  } catch (error) {
    console.error('Failed to check command status:', error);
  }
}, 30000); // Every 30 seconds

module.exports = resolvers;