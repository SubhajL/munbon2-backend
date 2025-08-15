import { Router, Request, Response } from 'express';
import { scadaGateControlService } from '../services/scada-gate-control.service';
import { irrigationControllerService } from '../services/irrigation-controller.service';
import { logger } from '../utils/logger';
import axios from 'axios';

const router = Router();

/**
 * POST /api/irrigation/execute-schedule
 * Execute an irrigation schedule based on water demand
 */
router.post('/execute-schedule', async (req: Request, res: Response) => {
  try {
    const { scheduleId, date, waterDemand, duration, sections, autoAdjust } = req.body;
    
    const executionId = `exec-${new Date().toISOString().split('T')[0]}-${Date.now().toString(36)}`;
    
    logger.info(`Executing irrigation schedule ${scheduleId} for ${waterDemand}m³ over ${duration}s`);
    
    // Calculate flow rate needed
    const flowRateNeeded = waterDemand / (duration / 3600); // m³/hr
    
    // Determine gates to open based on sections
    const gatesToOpen = await determineGatesForSections(sections);
    
    // Get current water levels
    const waterLevels = await getCurrentWaterLevels();
    
    // Adjust gate openings based on water levels if autoAdjust is enabled
    let adjustedGates = gatesToOpen;
    if (autoAdjust) {
      adjustedGates = await adjustGateOpenings(gatesToOpen, waterLevels, flowRateNeeded);
    }
    
    // Open gates sequentially for safety
    const gateResults = [];
    for (const gate of adjustedGates) {
      try {
        const result = await scadaGateControlService.controlGate(gate.gateId, {
          targetOpening: gate.position,
          mode: 'auto',
          reason: `Schedule ${scheduleId}: ${waterDemand}m³ irrigation`,
          duration
        });
        
        gateResults.push({
          gateId: gate.gateId,
          action: 'opened',
          position: gate.position,
          flow: gate.estimatedFlow || calculateFlowForGate(gate.position, waterLevels.upstream)
        });
      } catch (error) {
        logger.error(`Failed to open gate ${gate.gateId}:`, error);
        gateResults.push({
          gateId: gate.gateId,
          action: 'failed',
          error: error instanceof Error ? error.message : 'Unknown error'
        });
      }
    }
    
    // Calculate total flow
    const totalFlow = gateResults
      .filter(g => g.action === 'opened')
      .reduce((sum, g) => sum + (g.flow || 0), 0);
    
    // Set up monitoring for water delivery
    startIrrigationMonitoring(executionId, waterDemand, duration);
    
    const response = {
      executionId,
      status: 'active',
      schedule: {
        start: new Date().toISOString(),
        end: new Date(Date.now() + duration * 1000).toISOString(),
        waterTarget: waterDemand,
        waterDelivered: 0, // Will be updated in real-time
        progress: 0
      },
      gates: gateResults,
      monitoring: {
        upstream_level: waterLevels.upstream,
        downstream_level: waterLevels.downstream,
        total_flow: totalFlow,
        efficiency: calculateEfficiency(totalFlow, flowRateNeeded)
      }
    };
    
    res.json(response);
  } catch (error: any) {
    logger.error('Failed to execute irrigation schedule:', error);
    res.status(500).json({
      success: false,
      error: error.message
    });
  }
});

/**
 * GET /api/irrigation/status/:executionId
 * Get status of ongoing irrigation execution
 */
router.get('/status/:executionId', async (req: Request, res: Response) => {
  try {
    const { executionId } = req.params;
    
    // Get execution status from monitoring system
    const status = await getIrrigationStatus(executionId);
    
    if (!status) {
      return res.status(404).json({
        error: 'Execution not found',
        executionId
      });
    }
    
    res.json(status);
  } catch (error: any) {
    logger.error('Failed to get irrigation status:', error);
    res.status(500).json({
      error: error.message
    });
  }
});

/**
 * POST /api/irrigation/stop/:executionId
 * Stop ongoing irrigation execution
 */
router.post('/stop/:executionId', async (req: Request, res: Response) => {
  try {
    const { executionId } = req.params;
    const { reason } = req.body;
    
    logger.info(`Stopping irrigation execution ${executionId}: ${reason}`);
    
    // Get current execution status
    const status = await getIrrigationStatus(executionId);
    
    if (!status) {
      return res.status(404).json({
        error: 'Execution not found',
        executionId
      });
    }
    
    // Close all gates associated with this execution
    const closeResults = [];
    for (const gate of status.gates) {
      try {
        await scadaGateControlService.controlGate(gate.gateId, {
          targetOpening: 0,
          mode: 'manual',
          reason: `Stop execution: ${reason}`
        });
        closeResults.push({
          gateId: gate.gateId,
          status: 'closed'
        });
      } catch (error) {
        closeResults.push({
          gateId: gate.gateId,
          status: 'failed',
          error: error instanceof Error ? error.message : 'Unknown error'
        });
      }
    }
    
    // Stop monitoring
    stopIrrigationMonitoring(executionId);
    
    res.json({
      success: true,
      executionId,
      status: 'stopped',
      reason,
      gatesClosed: closeResults,
      waterDelivered: status.schedule.waterDelivered,
      efficiency: status.monitoring.efficiency
    });
  } catch (error: any) {
    logger.error('Failed to stop irrigation:', error);
    res.status(500).json({
      error: error.message
    });
  }
});

// Helper functions

async function determineGatesForSections(sections: string[]): Promise<any[]> {
  // Map sections to their respective gates
  const sectionGateMapping: Record<string, string[]> = {
    'section-1A': ['MG-01', 'SG-01'],
    'section-1B': ['MG-02', 'SG-02'],
    'section-2A': ['MG-03', 'SG-03'],
    'section-2B': ['MG-04', 'SG-04']
  };
  
  const gates = [];
  for (const section of sections) {
    const gateIds = sectionGateMapping[section] || [];
    for (const gateId of gateIds) {
      gates.push({
        gateId,
        position: 100, // Default to fully open
        priority: gateId.startsWith('MG') ? 1 : 2
      });
    }
  }
  
  return gates;
}

async function getCurrentWaterLevels(): Promise<any> {
  try {
    // Try to get real water levels from sensor service
    const response = await axios.get('http://localhost:3003/api/water-level/latest');
    return {
      upstream: response.data.upstream || 4.5,
      downstream: response.data.downstream || 3.2
    };
  } catch (error) {
    // Return default values if service unavailable
    return {
      upstream: 4.5,
      downstream: 3.2
    };
  }
}

async function adjustGateOpenings(gates: any[], waterLevels: any, targetFlow: number): Promise<any[]> {
  // Adjust gate openings based on water levels to achieve target flow
  const adjustedGates = [];
  
  for (const gate of gates) {
    // Calculate required opening based on water level difference
    const headDifference = waterLevels.upstream - waterLevels.downstream;
    const baseFlow = calculateFlowForGate(100, waterLevels.upstream);
    const requiredOpening = Math.min(100, (targetFlow / gates.length / baseFlow) * 100);
    
    adjustedGates.push({
      ...gate,
      position: Math.round(requiredOpening),
      estimatedFlow: calculateFlowForGate(requiredOpening, waterLevels.upstream)
    });
  }
  
  return adjustedGates;
}

function calculateFlowForGate(opening: number, upstreamLevel: number): number {
  // Simplified flow calculation based on opening percentage and water level
  // Flow = C * A * sqrt(2 * g * h)
  const C = 0.6; // Discharge coefficient
  const g = 9.81; // Gravity
  const gateArea = 2.0; // Gate area in m²
  const effectiveArea = gateArea * (opening / 100);
  const head = upstreamLevel;
  
  return C * effectiveArea * Math.sqrt(2 * g * head) * 3600; // Convert to m³/hr
}

function calculateEfficiency(actualFlow: number, targetFlow: number): number {
  if (targetFlow === 0) return 0;
  return Math.min(100, (actualFlow / targetFlow) * 100);
}

// Monitoring system (simplified)
const irrigationMonitors = new Map();

function startIrrigationMonitoring(executionId: string, targetVolume: number, duration: number) {
  const monitor = {
    executionId,
    targetVolume,
    duration,
    startTime: Date.now(),
    delivered: 0,
    flowReadings: []
  };
  
  // Simulate monitoring with periodic updates
  const interval = setInterval(() => {
    const elapsed = (Date.now() - monitor.startTime) / 1000;
    if (elapsed >= duration) {
      clearInterval(interval);
      monitor.status = 'completed';
    } else {
      // Simulate water delivery progress
      monitor.delivered = (elapsed / duration) * targetVolume;
    }
  }, 5000); // Update every 5 seconds
  
  monitor.interval = interval;
  irrigationMonitors.set(executionId, monitor);
}

function stopIrrigationMonitoring(executionId: string) {
  const monitor = irrigationMonitors.get(executionId);
  if (monitor) {
    clearInterval(monitor.interval);
    monitor.status = 'stopped';
  }
}

async function getIrrigationStatus(executionId: string): Promise<any> {
  const monitor = irrigationMonitors.get(executionId);
  if (!monitor) return null;
  
  const elapsed = (Date.now() - monitor.startTime) / 1000;
  const progress = Math.min(100, (elapsed / monitor.duration) * 100);
  
  return {
    executionId,
    status: monitor.status || 'active',
    schedule: {
      waterTarget: monitor.targetVolume,
      waterDelivered: monitor.delivered,
      progress
    },
    gates: [], // Would be populated from actual gate status
    monitoring: {
      upstream_level: 4.5,
      downstream_level: 3.2,
      total_flow: 210.7,
      efficiency: 92.5
    }
  };
}

export default router;
export const irrigationRouter = router;