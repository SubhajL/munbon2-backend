import { Request, Response, NextFunction } from 'express';
import { parcelService } from '../services/parcel.service';
import { logger } from '../utils/logger';
import { ApiError } from '../utils/api-error';

class ParcelController {
  async getAllParcels(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { 
        page = 1, 
        limit = 100, 
        includeGeometry = false,
        zoneId,
        landUseType,
        irrigationStatus 
      } = req.query;

      const parcels = await parcelService.getAllParcels({
        page: Number(page),
        limit: Number(limit),
        includeGeometry: includeGeometry === 'true',
        filters: {
          zoneId: zoneId as string,
          landUseType: landUseType as string,
          irrigationStatus: irrigationStatus as string,
        },
      });

      res.json({
        success: true,
        data: parcels,
      });
    } catch (error) {
      next(error);
    }
  }

  async getParcelById(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { id } = req.params;
      const parcel = await parcelService.getParcelById(id);

      if (!parcel) {
        throw new ApiError(404, 'Parcel not found');
      }

      res.json({
        success: true,
        data: parcel,
      });
    } catch (error) {
      next(error);
    }
  }

  async queryParcels(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const parcels = await parcelService.queryParcels(req.body);

      res.json({
        success: true,
        data: parcels,
        count: parcels.length,
      });
    } catch (error) {
      next(error);
    }
  }

  async getParcelHistory(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { id } = req.params;
      const { startDate, endDate } = req.query;

      const history = await parcelService.getParcelHistory(id, {
        startDate: startDate as string,
        endDate: endDate as string,
      });

      res.json({
        success: true,
        data: history,
      });
    } catch (error) {
      next(error);
    }
  }

  async getParcelsByOwner(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { ownerId } = req.params;
      const { page = 1, limit = 50 } = req.query;

      const parcels = await parcelService.getParcelsByOwner(ownerId, {
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

  async getCropPlan(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { id } = req.params;
      const { season, year } = req.query;

      const cropPlan = await parcelService.getCropPlan(id, {
        season: season as string,
        year: year ? Number(year) : new Date().getFullYear(),
      });

      res.json({
        success: true,
        data: cropPlan,
      });
    } catch (error) {
      next(error);
    }
  }

  async updateCropPlan(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { id } = req.params;
      const cropPlan = await parcelService.updateCropPlan(id, req.body);

      res.json({
        success: true,
        data: cropPlan,
        message: 'Crop plan updated successfully',
      });
    } catch (error) {
      next(error);
    }
  }

  async createParcel(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const parcel = await parcelService.createParcel(req.body);

      res.status(201).json({
        success: true,
        data: parcel,
        message: 'Parcel created successfully',
      });
    } catch (error) {
      next(error);
    }
  }

  async updateParcel(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { id } = req.params;
      const parcel = await parcelService.updateParcel(id, req.body);

      res.json({
        success: true,
        data: parcel,
        message: 'Parcel updated successfully',
      });
    } catch (error) {
      next(error);
    }
  }

  async updateParcelGeometry(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { id } = req.params;
      const { geometry } = req.body;

      const parcel = await parcelService.updateParcelGeometry(id, geometry);

      res.json({
        success: true,
        data: parcel,
        message: 'Parcel geometry updated successfully',
      });
    } catch (error) {
      next(error);
    }
  }

  async transferOwnership(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { id } = req.params;
      const { newOwnerId, transferDate, notes } = req.body;

      const result = await parcelService.transferOwnership(id, {
        newOwnerId,
        transferDate,
        notes,
        transferredBy: req.user?.id,
      });

      res.json({
        success: true,
        data: result,
        message: 'Ownership transferred successfully',
      });
    } catch (error) {
      next(error);
    }
  }

  async deleteParcel(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { id } = req.params;
      await parcelService.deleteParcel(id);

      res.json({
        success: true,
        message: 'Parcel deleted successfully',
      });
    } catch (error) {
      next(error);
    }
  }

  async bulkImportParcels(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { format = 'geojson', zoneId } = req.query;
      const result = await parcelService.bulkImportParcels(req.body, {
        format: format as string,
        zoneId: zoneId as string,
      });

      res.json({
        success: true,
        data: result,
        message: `Successfully imported ${result.imported} parcels`,
      });
    } catch (error) {
      next(error);
    }
  }

  async bulkUpdateParcels(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { parcels } = req.body;
      const result = await parcelService.bulkUpdateParcels(parcels);

      res.json({
        success: true,
        data: result,
        message: `Successfully updated ${result.updated} parcels`,
      });
    } catch (error) {
      next(error);
    }
  }

  async mergeParcels(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { parcelIds, newParcelData } = req.body;
      const mergedParcel = await parcelService.mergeParcels(parcelIds, newParcelData);

      res.json({
        success: true,
        data: mergedParcel,
        message: 'Parcels merged successfully',
      });
    } catch (error) {
      next(error);
    }
  }

  async splitParcel(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { id } = req.params;
      const { splitGeometries, splitData } = req.body;

      const newParcels = await parcelService.splitParcel(id, {
        splitGeometries,
        splitData,
      });

      res.json({
        success: true,
        data: newParcels,
        message: 'Parcel split successfully',
      });
    } catch (error) {
      next(error);
    }
  }
}

export const parcelController = new ParcelController();