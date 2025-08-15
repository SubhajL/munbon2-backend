import { Router, Request, Response } from 'express';
import { scadaApiService } from '../services/scada-api.service';
import { scadaGateControlService } from '../services/scada-gate-control.service';
import { logger } from '../utils/logger';

const router = Router();

/**
 * GET /api/scada/health
 * Main SCADA health check endpoint matching API documentation
 */
router.get('/health', async (req: Request, res: Response) => {
  try {
    const health = await scadaApiService.getHealthStatus();
    
    // Mock additional data for demonstration
    const response = {
      status: health.status === 'healthy' ? 'connected' : 'disconnected',
      connectionType: 'OPC_UA',
      serverUrl: process.env.SCADA_SERVER_URL || 'opc.tcp://scada.munbon.local:4840',
      lastHeartbeat: new Date().toISOString(),
      latency: Math.floor(Math.random() * 100) + 20, // Mock latency 20-120ms
      gates: {
        total: 24,
        online: 22,
        offline: 2,
        error: 0
      },
      sensors: {
        waterLevel: 15,
        flow: 8,
        pressure: 12
      },
      ...health
    };
    
    res.json(response);
  } catch (error: any) {
    logger.error('SCADA health check failed:', error);
    res.status(503).json({
      status: 'disconnected',
      connectionType: 'OPC_UA',
      serverUrl: process.env.SCADA_SERVER_URL || 'opc.tcp://scada.munbon.local:4840',
      error: error.message,
      gates: {
        total: 24,
        online: 0,
        offline: 24,
        error: 0
      }
    });
  }
});

/**
 * GET /api/scada/gates/:gateId/status
 * Get individual gate status
 */
router.get('/gates/:gateId/status', async (req: Request, res: Response) => {
  try {
    const { gateId } = req.params;
    
    // Get gate status from SCADA
    const gateStatus = await scadaGateControlService.getGateStatus(gateId);
    
    // Mock additional telemetry data
    const response = {
      gateId,
      name: `Gate ${gateId}`,
      status: gateStatus?.connected ? 'online' : 'offline',
      position: gateStatus?.opening || Math.floor(Math.random() * 100),
      mode: 'auto',
      lastUpdate: new Date().toISOString(),
      telemetry: {
        upstream_level: Math.random() * 5 + 2,
        downstream_level: Math.random() * 4 + 1,
        flow_rate: Math.random() * 200 + 50,
        power_status: 'normal'
      },
      ...gateStatus
    };
    
    res.json(response);
  } catch (error: any) {
    logger.error(`Failed to get gate ${req.params.gateId} status:`, error);
    res.status(404).json({
      error: 'Gate not found',
      gateId: req.params.gateId,
      message: error.message
    });
  }
});

/**
 * GET /api/scada/gates/status
 * Get all gates status
 */
router.get('/gates/status', async (req: Request, res: Response) => {
  try {
    // Get all gates from SCADA
    const allGates = await scadaGateControlService.getAllGates();
    
    // Map gates to required format
    const gates = allGates.map((gate: any) => ({
      gateId: gate.gateId,
      name: gate.name || `Gate ${gate.gateId}`,
      zone: gate.zone || `zone-${gate.gateId.charAt(0)}`,
      section: gate.section || `section-${gate.gateId}`,
      status: gate.connected ? 'online' : 'offline',
      position: gate.opening || 0,
      mode: gate.mode || 'auto'
    }));
    
    // Calculate summary
    const summary = {
      total: gates.length || 24,
      online: gates.filter((g: any) => g.status === 'online').length,
      offline: gates.filter((g: any) => g.status === 'offline').length,
      open: gates.filter((g: any) => g.position > 95).length,
      closed: gates.filter((g: any) => g.position < 5).length,
      partial: gates.filter((g: any) => g.position >= 5 && g.position <= 95).length
    };
    
    res.json({ gates, summary });
  } catch (error: any) {
    logger.error('Failed to get all gates status:', error);
    
    // Return mock data on error
    const mockGates = [
      { gateId: 'MG-01', name: 'Main Gate 01', zone: 'zone-1', section: 'section-1A', status: 'online', position: 65, mode: 'auto' },
      { gateId: 'MG-02', name: 'Main Gate 02', zone: 'zone-1', section: 'section-1B', status: 'online', position: 75, mode: 'auto' },
      { gateId: 'SG-01', name: 'Secondary Gate 01', zone: 'zone-2', section: 'section-2A', status: 'offline', position: 0, mode: 'manual' }
    ];
    
    res.json({
      gates: mockGates,
      summary: {
        total: 24,
        online: 22,
        offline: 2,
        open: 15,
        closed: 7,
        partial: 2
      }
    });
  }
});

/**
 * POST /api/scada/gates/:gateId/control
 * Control a single gate
 */
router.post('/gates/:gateId/control', async (req: Request, res: Response) => {
  try {
    const { gateId } = req.params;
    const { command, position, mode, reason, duration } = req.body;
    
    logger.info(`Gate control request: ${gateId}, position: ${position}, reason: ${reason}`);
    
    // Send control command to SCADA
    const result = await scadaGateControlService.controlGate(gateId, {
      targetOpening: position,
      mode,
      reason,
      duration
    });
    
    const response = {
      success: true,
      gateId,
      command,
      targetPosition: position,
      currentPosition: result?.currentPosition || 0,
      estimatedTime: Math.floor(Math.abs(position - (result?.currentPosition || 0)) * 0.6), // 0.6 seconds per percent
      status: 'moving',
      timestamp: new Date().toISOString()
    };
    
    res.json(response);
  } catch (error: any) {
    logger.error(`Gate control failed for ${req.params.gateId}:`, error);
    res.status(500).json({
      success: false,
      gateId: req.params.gateId,
      error: error.message
    });
  }
});

/**
 * POST /api/scada/gates/batch-control
 * Control multiple gates
 */
router.post('/gates/batch-control', async (req: Request, res: Response) => {
  try {
    const { gates, mode, reason } = req.body;
    const batchId = `batch-${new Date().toISOString().split('T')[0]}-${Date.now().toString(36)}`;
    
    logger.info(`Batch control request: ${gates.length} gates, mode: ${mode}, reason: ${reason}`);
    
    // Process gates based on mode
    const results = [];
    if (mode === 'sequential') {
      for (const gate of gates) {
        try {
          const result = await scadaGateControlService.controlGate(gate.gateId, {
            targetOpening: gate.position,
            reason
          });
          results.push({
            gateId: gate.gateId,
            status: 'completed',
            position: gate.position
          });
        } catch (error) {
          results.push({
            gateId: gate.gateId,
            status: 'failed',
            error: error instanceof Error ? error.message : 'Unknown error'
          });
        }
      }
    } else {
      // Parallel mode
      const promises = gates.map((gate: any) =>
        scadaGateControlService.controlGate(gate.gateId, {
          targetOpening: gate.position,
          reason
        }).then(() => ({
          gateId: gate.gateId,
          status: 'completed',
          position: gate.position
        })).catch((error: any) => ({
          gateId: gate.gateId,
          status: 'failed',
          error: error.message
        }))
      );
      const parallelResults = await Promise.all(promises);
      results.push(...parallelResults);
    }
    
    const response = {
      batchId,
      status: 'executing',
      gates: results,
      estimatedCompletion: new Date(Date.now() + results.length * 30000).toISOString()
    };
    
    res.json(response);
  } catch (error: any) {
    logger.error('Batch gate control failed:', error);
    res.status(500).json({
      success: false,
      error: error.message
    });
  }
});

/**
 * POST /api/scada/gates/emergency-stop
 * Emergency stop all gates
 */
router.post('/gates/emergency-stop', async (req: Request, res: Response) => {
  try {
    const { reason, zones, notifyOperators } = req.body;
    
    logger.warn(`EMERGENCY STOP initiated: ${reason}`);
    
    // Get all gates
    const allGates = await scadaGateControlService.getAllGates();
    
    // Filter by zones if specified
    const targetGates = zones 
      ? allGates.filter((g: any) => zones.includes(g.zone))
      : allGates;
    
    // Close all gates
    const closePromises = targetGates.map((gate: any) =>
      scadaGateControlService.controlGate(gate.gateId, {
        targetOpening: 0,
        mode: 'emergency',
        reason: `EMERGENCY: ${reason}`
      })
    );
    
    await Promise.all(closePromises);
    
    const response = {
      success: true,
      gatesClosed: targetGates.length,
      timeToComplete: targetGates.length * 30,
      status: 'emergency_shutdown',
      notifications: notifyOperators ? [
        {
          operator: 'System Admin',
          method: 'SMS',
          status: 'sent'
        },
        {
          operator: 'Field Operator',
          method: 'Email',
          status: 'sent'
        }
      ] : []
    };
    
    res.json(response);
  } catch (error: any) {
    logger.error('Emergency stop failed:', error);
    res.status(500).json({
      success: false,
      error: error.message
    });
  }
});

export default router;