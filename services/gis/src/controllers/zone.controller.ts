import { Request, Response, NextFunction } from 'express';
import { zoneService } from '../services/zone.service';
import { logger } from '../utils/logger';
import { ApiError } from '../utils/api-error';

class ZoneController {
  async getAllZones(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { page = 1, limit = 50, includeGeometry = false } = req.query;
      
      const zones = await zoneService.getAllZones({
        page: Number(page),
        limit: Number(limit),
        includeGeometry: includeGeometry === 'true',
      });

      res.json({
        success: true,
        data: zones,
      });
    } catch (error) {
      next(error);
    }
  }

  async getZoneById(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { id } = req.params;
      const zone = await zoneService.getZoneById(id);

      if (!zone) {
        throw new ApiError(404, 'Zone not found');
      }

      res.json({
        success: true,
        data: zone,
      });
    } catch (error) {
      next(error);
    }
  }

  async queryZones(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const zones = await zoneService.queryZones(req.body);

      res.json({
        success: true,
        data: zones,
        count: zones.length,
      });
    } catch (error) {
      next(error);
    }
  }

  async getZoneStatistics(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { id } = req.params;
      const stats = await zoneService.getZoneStatistics(id);

      res.json({
        success: true,
        data: stats,
      });
    } catch (error) {
      next(error);
    }
  }

  async getParcelsInZone(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { id } = req.params;
      const { page = 1, limit = 100 } = req.query;

      const parcels = await zoneService.getParcelsInZone(id, {
        page: Number(page),
        limit: Number(limit),
      });

      res.json({
        success: true,
        data: parcels,
      });
    } catch (error) {
      next(error);
    }
  }

  async getWaterDistribution(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { id } = req.params;
      const { startDate, endDate } = req.query;

      const distribution = await zoneService.getWaterDistribution(id, {
        startDate: startDate as string,
        endDate: endDate as string,
      });

      res.json({
        success: true,
        data: distribution,
      });
    } catch (error) {
      next(error);
    }
  }

  async createZone(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const zone = await zoneService.createZone(req.body);

      res.status(201).json({
        success: true,
        data: zone,
        message: 'Zone created successfully',
      });
    } catch (error) {
      next(error);
    }
  }

  async updateZone(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { id } = req.params;
      const zone = await zoneService.updateZone(id, req.body);

      res.json({
        success: true,
        data: zone,
        message: 'Zone updated successfully',
      });
    } catch (error) {
      next(error);
    }
  }

  async updateZoneGeometry(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { id } = req.params;
      const { geometry } = req.body;

      const zone = await zoneService.updateZoneGeometry(id, geometry);

      res.json({
        success: true,
        data: zone,
        message: 'Zone geometry updated successfully',
      });
    } catch (error) {
      next(error);
    }
  }

  async deleteZone(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { id } = req.params;
      await zoneService.deleteZone(id);

      res.json({
        success: true,
        message: 'Zone deleted successfully',
      });
    } catch (error) {
      next(error);
    }
  }

  async bulkImportZones(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { format = 'geojson' } = req.query;
      const result = await zoneService.bulkImportZones(req.body, format as string);

      res.json({
        success: true,
        data: result,
        message: `Successfully imported ${result.imported} zones`,
      });
    } catch (error) {
      next(error);
    }
  }

  async bulkUpdateZones(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { zones } = req.body;
      const result = await zoneService.bulkUpdateZones(zones);

      res.json({
        success: true,
        data: result,
        message: `Successfully updated ${result.updated} zones`,
      });
    } catch (error) {
      next(error);
    }
  }
}

export const zoneController = new ZoneController();