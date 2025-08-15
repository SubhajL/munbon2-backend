import { Router, Request, Response } from 'express';
import { gateCommandService } from '../services/gate-command.service';
import { GateCommand } from '../types/scada.types';

const router = Router();

/**
 * GET /api/v1/scada/sites
 * Get all available control sites
 */
router.get('/sites', async (req: Request, res: Response) => {
  try {
    const sites = await gateCommandService.getControlSites();
    res.json({
      sites,
      count: sites.length,
      timestamp: new Date()
    });
  } catch (error: any) {
    console.error('Error getting control sites:', error);
    res.status(500).json({
      message: 'Failed to get control sites',
      error: error.message
    });
  }
});

/**
 * POST /api/v1/scada/command/send
 * Send gate control command
 */
router.post('/command/send', async (req: Request, res: Response) => {
  try {
    const { gate_name, gate_level, fieldId, targetFlowRate } = req.body;
    
    // Validate required fields
    if (!gate_name || gate_level === undefined) {
      return res.status(400).json({
        message: 'Missing required fields: gate_name and gate_level'
      });
    }

    const command: GateCommand = {
      gate_name,
      gate_level: Number(gate_level),
      startdatetime: new Date(),
      fieldId,
      targetFlowRate
    };

    const result = await gateCommandService.sendGateCommand(command);
    
    if (result.success) {
      res.json(result);
    } else {
      res.status(400).json(result);
    }
  } catch (error: any) {
    console.error('Error sending gate command:', error);
    res.status(500).json({
      success: false,
      message: 'Failed to send gate command',
      error: error.message
    });
  }
});

/**
 * GET /api/v1/scada/command/:id/status
 * Get command status by ID
 */
router.get('/command/:id/status', async (req: Request, res: Response) => {
  try {
    const commandId = parseInt(req.params.id);
    
    if (isNaN(commandId)) {
      return res.status(400).json({
        message: 'Invalid command ID'
      });
    }

    const status = await gateCommandService.getCommandStatus(commandId);
    
    if (!status) {
      return res.status(404).json({
        message: `Command ${commandId} not found`
      });
    }

    res.json({
      ...status,
      isComplete: status.completestatus === 1,
      timestamp: new Date()
    });
  } catch (error: any) {
    console.error('Error getting command status:', error);
    res.status(500).json({
      message: 'Failed to get command status',
      error: error.message
    });
  }
});

/**
 * GET /api/v1/scada/commands/recent
 * Get recent gate commands
 */
router.get('/commands/recent', async (req: Request, res: Response) => {
  try {
    const limit = parseInt(req.query.limit as string) || 50;
    const commands = await gateCommandService.getRecentCommands(limit);
    
    res.json({
      commands,
      count: commands.length,
      timestamp: new Date()
    });
  } catch (error: any) {
    console.error('Error getting recent commands:', error);
    res.status(500).json({
      message: 'Failed to get recent commands',
      error: error.message
    });
  }
});

/**
 * GET /api/v1/scada/commands/pending
 * Get pending (incomplete) commands
 */
router.get('/commands/pending', async (req: Request, res: Response) => {
  try {
    const commands = await gateCommandService.getPendingCommands();
    
    res.json({
      commands,
      count: commands.length,
      timestamp: new Date()
    });
  } catch (error: any) {
    console.error('Error getting pending commands:', error);
    res.status(500).json({
      message: 'Failed to get pending commands',
      error: error.message
    });
  }
});

/**
 * POST /api/v1/scada/gates/:gateName/close
 * Convenience endpoint to close a gate
 */
router.post('/gates/:gateName/close', async (req: Request, res: Response) => {
  try {
    const { gateName } = req.params;
    const { fieldId } = req.body;

    const command: GateCommand = {
      gate_name: gateName,
      gate_level: 1, // Closed
      startdatetime: new Date(),
      fieldId
    };

    const result = await gateCommandService.sendGateCommand(command);
    
    if (result.success) {
      res.json({
        ...result,
        action: 'close'
      });
    } else {
      res.status(400).json(result);
    }
  } catch (error: any) {
    console.error('Error closing gate:', error);
    res.status(500).json({
      success: false,
      message: 'Failed to close gate',
      error: error.message
    });
  }
});

/**
 * POST /api/v1/scada/gates/:gateName/open
 * Convenience endpoint to open a gate to specified level
 */
router.post('/gates/:gateName/open', async (req: Request, res: Response) => {
  try {
    const { gateName } = req.params;
    const { level = 2, fieldId, targetFlowRate } = req.body;

    const gateLevel = Number(level);
    if (gateLevel < 2 || gateLevel > 4) {
      return res.status(400).json({
        message: 'Invalid gate level for opening. Must be between 2 and 4'
      });
    }

    const command: GateCommand = {
      gate_name: gateName,
      gate_level: gateLevel,
      startdatetime: new Date(),
      fieldId,
      targetFlowRate
    };

    const result = await gateCommandService.sendGateCommand(command);
    
    if (result.success) {
      res.json({
        ...result,
        action: 'open',
        level: gateLevel
      });
    } else {
      res.status(400).json(result);
    }
  } catch (error: any) {
    console.error('Error opening gate:', error);
    res.status(500).json({
      success: false,
      message: 'Failed to open gate',
      error: error.message
    });
  }
});

export default router;