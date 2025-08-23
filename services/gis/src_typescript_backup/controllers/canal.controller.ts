import { Request, Response, NextFunction } from 'express';
import { canalService } from '../services/canal.service';
import { logger } from '../utils/logger';
import { ApiError } from '../utils/api-error';

class CanalController {
  async getAllCanals(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { 
        page = 1, 
        limit = 100, 
        includeGeometry = false,
        type,
        status,
        level 
      } = req.query;

      const canals = await canalService.getAllCanals({
        page: Number(page),
        limit: Number(limit),
        includeGeometry: includeGeometry === 'true',
        filters: {
          type: type as string,
          status: status as string,
          level: level ? Number(level) : undefined,
        },
      });

      res.json({
        success: true,
        data: canals,
      });
    } catch (error) {
      next(error);
    }
  }

  async getCanalById(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { id } = req.params;
      const canal = await canalService.getCanalById(id);

      if (!canal) {
        throw new ApiError(404, 'Canal not found');
      }

      res.json({
        success: true,
        data: canal,
      });
    } catch (error) {
      next(error);
    }
  }

  async queryCanals(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const canals = await canalService.queryCanals(req.body);

      res.json({
        success: true,
        data: canals,
        count: canals.length,
      });
    } catch (error) {
      next(error);
    }
  }

  async getFlowHistory(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { id } = req.params;
      const { startDate, endDate, interval = '1h' } = req.query;

      const history = await canalService.getFlowHistory(id, {
        startDate: startDate as string,
        endDate: endDate as string,
        interval: interval as string,
      });

      res.json({
        success: true,
        data: history,
      });
    } catch (error) {
      next(error);
    }
  }

  async getConnectedGates(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { id } = req.params;
      const gates = await canalService.getConnectedGates(id);

      res.json({
        success: true,
        data: gates,
        count: gates.length,
      });
    } catch (error) {
      next(error);
    }
  }

  async getNetworkTopology(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { startNodeId, depth = 3 } = req.query;
      
      const topology = await canalService.getNetworkTopology({
        startNodeId: startNodeId as string,
        depth: Number(depth),
      });

      res.json({
        success: true,
        data: topology,
      });
    } catch (error) {
      next(error);
    }
  }

  async updateCanalStatus(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { id } = req.params;
      const { status, reason } = req.body;

      const canal = await canalService.updateCanalStatus(id, {
        status,
        reason,
        updatedBy: req.user?.id,
      });

      res.json({
        success: true,
        data: canal,
        message: 'Canal status updated successfully',
      });
    } catch (error) {
      next(error);
    }
  }

  async updateFlowRate(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { id } = req.params;
      const { flowRate, measuredAt, sensorId } = req.body;

      const result = await canalService.updateFlowRate(id, {
        flowRate,
        measuredAt,
        sensorId,
        recordedBy: req.user?.id,
      });

      res.json({
        success: true,
        data: result,
        message: 'Flow rate recorded successfully',
      });
    } catch (error) {
      next(error);
    }
  }

  async getMaintenanceHistory(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { id } = req.params;
      const { page = 1, limit = 20 } = req.query;

      const history = await canalService.getMaintenanceHistory(id, {
        page: Number(page),
        limit: Number(limit),
      });

      res.json({
        success: true,
        data: history,
      });
    } catch (error) {
      next(error);
    }
  }

  async createCanal(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const canal = await canalService.createCanal(req.body);

      res.status(201).json({
        success: true,
        data: canal,
        message: 'Canal created successfully',
      });
    } catch (error) {
      next(error);
    }
  }

  async updateCanal(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { id } = req.params;
      const canal = await canalService.updateCanal(id, req.body);

      res.json({
        success: true,
        data: canal,
        message: 'Canal updated successfully',
      });
    } catch (error) {
      next(error);
    }
  }

  async updateCanalGeometry(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { id } = req.params;
      const { geometry } = req.body;

      const canal = await canalService.updateCanalGeometry(id, geometry);

      res.json({
        success: true,
        data: canal,
        message: 'Canal geometry updated successfully',
      });
    } catch (error) {
      next(error);
    }
  }

  async deleteCanal(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { id } = req.params;
      await canalService.deleteCanal(id);

      res.json({
        success: true,
        message: 'Canal deleted successfully',
      });
    } catch (error) {
      next(error);
    }
  }

  async analyzeNetwork(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { sourceId, targetIds, analysisType } = req.body;

      const analysis = await canalService.analyzeNetwork({
        sourceId,
        targetIds,
        analysisType,
      });

      res.json({
        success: true,
        data: analysis,
      });
    } catch (error) {
      next(error);
    }
  }

  async optimizeFlow(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { constraints, objectives } = req.body;

      const optimization = await canalService.optimizeFlow({
        constraints,
        objectives,
      });

      res.json({
        success: true,
        data: optimization,
      });
    } catch (error) {
      next(error);
    }
  }

  async identifyBottlenecks(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { threshold = 0.8, includeRecommendations = true } = req.query;

      const bottlenecks = await canalService.identifyBottlenecks({
        threshold: Number(threshold),
        includeRecommendations: includeRecommendations === 'true',
      });

      res.json({
        success: true,
        data: bottlenecks,
        count: bottlenecks.length,
      });
    } catch (error) {
      next(error);
    }
  }

  async bulkImportCanals(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { format = 'geojson' } = req.query;
      const result = await canalService.bulkImportCanals(req.body, format as string);

      res.json({
        success: true,
        data: result,
        message: `Successfully imported ${result.imported} canals`,
      });
    } catch (error) {
      next(error);
    }
  }

  async bulkUpdateCanals(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { canals } = req.body;
      const result = await canalService.bulkUpdateCanals(canals);

      res.json({
        success: true,
        data: result,
        message: `Successfully updated ${result.updated} canals`,
      });
    } catch (error) {
      next(error);
    }
  }
}

export const canalController = new CanalController();