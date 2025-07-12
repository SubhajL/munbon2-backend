import { Request, Response, NextFunction } from 'express';
import { spatialService } from '../services/spatial.service';
import { logger } from '../utils/logger';
import { ApiError } from '../utils/api-error';
import * as turf from '@turf/turf';

class SpatialController {
  async queryByBounds(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { tableName, bounds, properties } = req.body;

      const features = await spatialService.findWithinBounds(
        tableName,
        bounds,
        properties
      );

      res.json({
        success: true,
        data: features,
        count: features.features.length,
      });
    } catch (error) {
      next(error);
    }
  }

  async queryByDistance(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { tableName, center, distance, unit, properties } = req.body;

      const features = await spatialService.findWithinDistance(
        tableName,
        center,
        distance,
        unit,
        properties
      );

      res.json({
        success: true,
        data: features,
        count: features.features.length,
      });
    } catch (error) {
      next(error);
    }
  }

  async queryByIntersection(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { tableName, geometry, properties } = req.body;

      const features = await spatialService.findIntersecting(
        tableName,
        geometry,
        properties
      );

      res.json({
        success: true,
        data: features,
        count: features.features.length,
      });
    } catch (error) {
      next(error);
    }
  }

  async buffer(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { geometry, distance, unit, options } = req.body;

      const buffered = await spatialService.buffer(
        geometry,
        { distance, unit, ...options }
      );

      res.json({
        success: true,
        data: buffered,
      });
    } catch (error) {
      next(error);
    }
  }

  async union(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { geometries } = req.body;

      const unioned = await spatialService.union(geometries);

      res.json({
        success: true,
        data: unioned,
      });
    } catch (error) {
      next(error);
    }
  }

  async intersection(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { geometry1, geometry2 } = req.body;

      const intersection = await spatialService.intersection(geometry1, geometry2);

      res.json({
        success: true,
        data: intersection,
      });
    } catch (error) {
      next(error);
    }
  }

  async simplify(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { geometry, tolerance, highQuality } = req.body;

      const simplified = await spatialService.simplify(
        geometry,
        tolerance || 0.01,
        highQuality !== false
      );

      res.json({
        success: true,
        data: simplified,
      });
    } catch (error) {
      next(error);
    }
  }

  async transform(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { geometry, fromSrid, toSrid } = req.body;

      const transformed = await spatialService.transform(
        geometry,
        fromSrid || 4326,
        toSrid || 32647 // UTM Zone 47N for Thailand
      );

      res.json({
        success: true,
        data: transformed,
      });
    } catch (error) {
      next(error);
    }
  }

  async calculateArea(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { geometry, unit } = req.body;

      const area = await spatialService.calculateArea(geometry, unit);

      res.json({
        success: true,
        data: {
          area,
          unit: unit || 'hectares',
        },
      });
    } catch (error) {
      next(error);
    }
  }

  async calculateLength(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { geometry, unit } = req.body;

      const length = await spatialService.calculateLength(geometry, unit);

      res.json({
        success: true,
        data: {
          length,
          unit: unit || 'meters',
        },
      });
    } catch (error) {
      next(error);
    }
  }

  async calculateDistance(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { point1, point2, unit } = req.body;

      const distance = turf.distance(
        turf.point(point1),
        turf.point(point2),
        { units: unit || 'meters' }
      );

      res.json({
        success: true,
        data: {
          distance,
          unit: unit || 'meters',
        },
      });
    } catch (error) {
      next(error);
    }
  }

  async getElevation(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { lng, lat } = req.params;

      const elevation = await spatialService.getElevation(
        Number(lng),
        Number(lat)
      );

      res.json({
        success: true,
        data: {
          longitude: Number(lng),
          latitude: Number(lat),
          elevation,
          unit: 'meters',
        },
      });
    } catch (error) {
      next(error);
    }
  }
}

export const spatialController = new SpatialController();