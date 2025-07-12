import { Request, Response, NextFunction } from 'express';
import { ShapeFileService } from '../services/shapefile.service';
import { ApiError } from '../utils/api-error';
import { logger } from '../utils/logger';

export class ShapeFileController {
  private shapeFileService: ShapeFileService;

  constructor() {
    this.shapeFileService = new ShapeFileService();
  }

  uploadShapeFile = async (req: Request, res: Response, next: NextFunction) => {
    try {
      if (!req.file) {
        throw new ApiError(400, 'No file uploaded');
      }

      const uploadResult = await this.shapeFileService.processUpload({
        file: req.file,
        waterDemandMethod: req.body.waterDemandMethod || 'RID-MS',
        processingInterval: req.body.processingInterval || 'weekly',
        metadata: {
          uploadedBy: req.user?.id || 'unknown',
          description: req.body.description,
          zone: req.body.zone,
          ...req.body.metadata,
        },
      });

      res.status(202).json({
        success: true,
        message: 'Shape file uploaded and queued for processing',
        data: uploadResult,
      });
    } catch (error) {
      next(error);
    }
  };

  externalUpload = async (req: Request, res: Response, next: NextFunction) => {
    try {
      // Validate bearer token for external access
      const authHeader = req.headers.authorization;
      if (!authHeader || !authHeader.startsWith('Bearer ')) {
        throw new ApiError(401, 'Missing authorization header');
      }

      const token = authHeader.substring(7);
      if (token !== process.env.EXTERNAL_UPLOAD_TOKEN) {
        throw new ApiError(403, 'Invalid authorization token');
      }

      if (!req.file) {
        throw new ApiError(400, 'No file uploaded');
      }

      const uploadResult = await this.shapeFileService.processUpload({
        file: req.file,
        waterDemandMethod: req.body.waterDemandMethod || 'RID-MS',
        processingInterval: req.body.processingInterval || 'weekly',
        metadata: {
          uploadedBy: 'external-api',
          source: 'rid-ms',
          description: req.body.description,
          zone: req.body.zone,
          ...req.body.metadata,
        },
      });

      res.status(202).json({
        success: true,
        message: 'Shape file uploaded successfully',
        uploadId: uploadResult.uploadId,
        fileName: uploadResult.fileName,
        uploadedAt: uploadResult.uploadedAt,
      });
    } catch (error) {
      next(error);
    }
  };

  listUploads = async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { page = 1, limit = 20, status, startDate, endDate } = req.query;

      const uploads = await this.shapeFileService.listUploads({
        page: Number(page),
        limit: Number(limit),
        status: status as string,
        startDate: startDate as string,
        endDate: endDate as string,
      });

      res.json({
        success: true,
        data: uploads,
      });
    } catch (error) {
      next(error);
    }
  };

  getUploadStatus = async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { uploadId } = req.params;
      
      const status = await this.shapeFileService.getUploadStatus(uploadId);
      
      if (!status) {
        throw new ApiError(404, 'Upload not found');
      }

      res.json({
        success: true,
        data: status,
      });
    } catch (error) {
      next(error);
    }
  };

  getUploadParcels = async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { uploadId } = req.params;
      const { format = 'json' } = req.query;

      const parcels = await this.shapeFileService.getUploadParcels(uploadId);

      if (format === 'geojson') {
        res.json({
          type: 'FeatureCollection',
          features: parcels.map(parcel => ({
            type: 'Feature',
            id: parcel.id,
            geometry: parcel.geometry,
            properties: {
              parcelCode: parcel.parcelCode,
              zoneId: parcel.zoneId,
              area: parcel.area,
              ownerName: parcel.ownerName,
              landUseType: parcel.landUseType,
              status: parcel.status,
            },
          })),
        });
      } else {
        res.json({
          success: true,
          data: parcels,
        });
      }
    } catch (error) {
      next(error);
    }
  };

  deleteUpload = async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { uploadId } = req.params;
      
      await this.shapeFileService.deleteUpload(uploadId);

      res.json({
        success: true,
        message: 'Upload and associated parcels deleted successfully',
      });
    } catch (error) {
      next(error);
    }
  };
}