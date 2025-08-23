import { Request, Response, NextFunction } from 'express';
import { areaService } from '@services/area.service';
import { AreaInfo, AreaType } from '@types/index';
import { logger } from '@utils/logger';

class AreaController {
  /**
   * Create a new area
   */
  async createArea(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const areaInfo: AreaInfo = req.body;
      const area = await areaService.createArea(areaInfo);

      res.status(201).json({
        success: true,
        data: area,
      });
    } catch (error) {
      logger.error('Error creating area', error);
      next(error);
    }
  }

  /**
   * Get area by ID
   */
  async getAreaById(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { areaId } = req.params;
      const area = await areaService.getAreaById(areaId);

      if (!area) {
        res.status(404).json({
          success: false,
          message: `Area ${areaId} not found`,
        });
        return;
      }

      res.status(200).json({
        success: true,
        data: area,
      });
    } catch (error) {
      logger.error('Error getting area', error);
      next(error);
    }
  }

  /**
   * Get areas by type
   */
  async getAreasByType(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { areaType } = req.params;
      const areas = await areaService.getAreasByType(areaType as AreaType);

      res.status(200).json({
        success: true,
        data: areas,
        count: areas.length,
      });
    } catch (error) {
      logger.error('Error getting areas by type', error);
      next(error);
    }
  }

  /**
   * Get child areas
   */
  async getChildAreas(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { areaId } = req.params;
      const childAreas = await areaService.getChildAreas(areaId);

      res.status(200).json({
        success: true,
        data: childAreas,
        count: childAreas.length,
      });
    } catch (error) {
      logger.error('Error getting child areas', error);
      next(error);
    }
  }

  /**
   * Update area
   */
  async updateArea(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { areaId } = req.params;
      const updates: Partial<AreaInfo> = req.body;

      const area = await areaService.updateArea(areaId, updates);

      if (!area) {
        res.status(404).json({
          success: false,
          message: `Area ${areaId} not found`,
        });
        return;
      }

      res.status(200).json({
        success: true,
        data: area,
      });
    } catch (error) {
      logger.error('Error updating area', error);
      next(error);
    }
  }

  /**
   * Delete area
   */
  async deleteArea(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { areaId } = req.params;
      const deleted = await areaService.deleteArea(areaId);

      if (!deleted) {
        res.status(404).json({
          success: false,
          message: `Area ${areaId} not found`,
        });
        return;
      }

      res.status(200).json({
        success: true,
        message: `Area ${areaId} deleted successfully`,
      });
    } catch (error) {
      logger.error('Error deleting area', error);
      next(error);
    }
  }

  /**
   * Get area hierarchy
   */
  async getAreaHierarchy(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { projectId } = req.params;
      const hierarchy = await areaService.getAreaHierarchy(projectId);

      res.status(200).json({
        success: true,
        data: hierarchy,
      });
    } catch (error) {
      logger.error('Error getting area hierarchy', error);
      next(error);
    }
  }

  /**
   * Calculate total area
   */
  async calculateTotalArea(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { areaId } = req.params;
      const totalArea = await areaService.calculateTotalArea(areaId);

      res.status(200).json({
        success: true,
        data: {
          parentAreaId: areaId,
          totalAreaRai: totalArea,
        },
      });
    } catch (error) {
      logger.error('Error calculating total area', error);
      next(error);
    }
  }

  /**
   * Import areas
   */
  async importAreas(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const areas: AreaInfo[] = req.body.areas;
      
      if (!Array.isArray(areas)) {
        res.status(400).json({
          success: false,
          message: 'Areas must be an array',
        });
        return;
      }

      const result = await areaService.importAreas(areas);

      res.status(200).json({
        success: true,
        data: result,
      });
    } catch (error) {
      logger.error('Error importing areas', error);
      next(error);
    }
  }

  /**
   * Get area statistics
   */
  async getAreaStatistics(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const stats = await areaService.getAreaStatistics();

      res.status(200).json({
        success: true,
        data: stats,
      });
    } catch (error) {
      logger.error('Error getting area statistics', error);
      next(error);
    }
  }
}

export const areaController = new AreaController();