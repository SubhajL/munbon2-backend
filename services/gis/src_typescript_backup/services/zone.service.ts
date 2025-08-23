import { Repository, DeepPartial } from 'typeorm';
import { AppDataSource } from '../config/database';
import { Zone, ZoneType, ZoneStatus } from '../models/zone.entity';
import { Parcel } from '../models/parcel.entity';
import { logger } from '../utils/logger';
import { ApiError } from '../utils/api-error';
import { cacheService } from './cache.service';
import { Feature, FeatureCollection, Polygon } from 'geojson';
import * as turf from '@turf/turf';

interface ZoneQuery {
  page: number;
  limit: number;
  includeGeometry?: boolean;
}

interface ZoneStatistics {
  totalArea: number;
  totalParcels: number;
  irrigatedArea: number;
  nonIrrigatedArea: number;
  cropTypes: Record<string, number>;
  waterUsage: {
    current: number;
    allocated: number;
    percentage: number;
  };
}

class ZoneService {
  private zoneRepository: Repository<Zone>;
  private parcelRepository: Repository<Parcel>;

  constructor() {
    this.zoneRepository = AppDataSource.getRepository(Zone);
    this.parcelRepository = AppDataSource.getRepository(Parcel);
  }

  async getAllZones(query: ZoneQuery): Promise<any> {
    const { page, limit, includeGeometry } = query;
    const skip = (page - 1) * limit;

    const cacheKey = `zones:all:${page}:${limit}:${includeGeometry}`;
    const cached = await cacheService.get(cacheKey);
    if (cached) return cached;

    const queryBuilder = this.zoneRepository
      .createQueryBuilder('zone')
      .select([
        'zone.id',
        'zone.code',
        'zone.name',
        'zone.type',
        'zone.area',
        'zone.totalParcels',
        'zone.irrigatedArea',
        'zone.waterAllocation',
        'zone.status',
      ]);

    if (includeGeometry) {
      queryBuilder.addSelect('zone.geometry');
    }

    const [zones, total] = await queryBuilder
      .skip(skip)
      .take(limit)
      .getManyAndCount();

    const result = {
      zones,
      pagination: {
        page,
        limit,
        total,
        pages: Math.ceil(total / limit),
      },
    };

    await cacheService.set(cacheKey, result, 300); // 5 minutes
    return result;
  }

  async getZoneById(id: string): Promise<Zone | null> {
    const cacheKey = `zone:${id}`;
    const cached = await cacheService.get(cacheKey);
    if (cached) return cached;

    const zone = await this.zoneRepository.findOne({
      where: { id },
      relations: ['canals', 'gates'],
    });

    if (zone) {
      await cacheService.set(cacheKey, zone, 600); // 10 minutes
    }

    return zone;
  }

  async queryZones(query: any): Promise<Zone[]> {
    const queryBuilder = this.zoneRepository.createQueryBuilder('zone');

    if (query.type) {
      queryBuilder.andWhere('zone.type = :type', { type: query.type });
    }

    if (query.status) {
      queryBuilder.andWhere('zone.status = :status', { status: query.status });
    }

    if (query.minArea) {
      queryBuilder.andWhere('zone.area >= :minArea', { minArea: query.minArea });
    }

    if (query.maxArea) {
      queryBuilder.andWhere('zone.area <= :maxArea', { maxArea: query.maxArea });
    }

    if (query.bounds) {
      const [minLng, minLat, maxLng, maxLat] = query.bounds;
      queryBuilder.andWhere(
        'ST_Intersects(zone.geometry, ST_MakeEnvelope(:minLng, :minLat, :maxLng, :maxLat, 4326))',
        { minLng, minLat, maxLng, maxLat }
      );
    }

    if (query.nearPoint) {
      const { lng, lat, distance } = query.nearPoint;
      queryBuilder.andWhere(
        'ST_DWithin(zone.geometry, ST_SetSRID(ST_Point(:lng, :lat), 4326), :distance)',
        { lng, lat, distance }
      );
    }

    return queryBuilder.getMany();
  }

  async getZoneStatistics(zoneId: string): Promise<ZoneStatistics> {
    const cacheKey = `zone:stats:${zoneId}`;
    const cached = await cacheService.get(cacheKey);
    if (cached) return cached;

    const zone = await this.zoneRepository.findOne({
      where: { id: zoneId },
    });

    if (!zone) {
      throw new ApiError(404, 'Zone not found');
    }

    // Get parcel statistics
    const parcels = await this.parcelRepository
      .createQueryBuilder('parcel')
      .where('parcel.zoneId = :zoneId', { zoneId })
      .getMany();

    const cropTypes: Record<string, number> = {};
    let irrigatedArea = 0;
    let nonIrrigatedArea = 0;

    parcels.forEach(parcel => {
      if (parcel.landUseType) {
        cropTypes[parcel.landUseType] = (cropTypes[parcel.landUseType] || 0) + parcel.area;
      }
      if (parcel.hasWaterAccess) {
        irrigatedArea += parcel.area;
      } else {
        nonIrrigatedArea += parcel.area;
      }
    });

    // Get water usage (would connect to sensor data service in production)
    const waterUsage = {
      current: irrigatedArea * 0.7, // Mock calculation
      allocated: zone.maxWaterAllocation || 0,
      percentage: zone.maxWaterAllocation ? (irrigatedArea * 0.7 / zone.maxWaterAllocation) * 100 : 0,
    };

    const stats: ZoneStatistics = {
      totalArea: zone.area,
      totalParcels: zone.statistics?.totalParcels || parcels.length,
      irrigatedArea,
      nonIrrigatedArea,
      cropTypes,
      waterUsage,
    };

    await cacheService.set(cacheKey, stats, 1800); // 30 minutes
    return stats;
  }

  async getParcelsInZone(zoneId: string, options: { page: number; limit: number }): Promise<any> {
    const { page, limit } = options;
    const skip = (page - 1) * limit;

    const [parcels, total] = await this.parcelRepository.findAndCount({
      where: { zone: { id: zoneId } },
      skip,
      take: limit,
      select: ['id', 'parcelCode', 'area', 'landUseType', 'ownerName', 'hasWaterAccess'],
    });

    return {
      parcels,
      pagination: {
        page,
        limit,
        total,
        pages: Math.ceil(total / limit),
      },
    };
  }

  async getWaterDistribution(zoneId: string, dateRange: any): Promise<any> {
    // This would integrate with water distribution control service
    // For now, return mock data
    return {
      zoneId,
      dateRange,
      totalAllocated: 1000000, // cubic meters
      totalUsed: 750000,
      distribution: [
        { date: '2024-01-01', allocated: 50000, used: 38000 },
        { date: '2024-01-02', allocated: 50000, used: 42000 },
        // ... more data
      ],
    };
  }

  async createZone(data: any): Promise<Zone> {
    const zone: Zone = this.zoneRepository.create({
      ...data,
      createdAt: new Date(),
      updatedAt: new Date(),
    });

    // Calculate area if geometry provided
    if (data.geometry) {
      const area = turf.area(data.geometry);
      zone.area = area / 10000; // Convert to hectares
    }

    const savedZone = await this.zoneRepository.save(zone as DeepPartial<Zone>) as unknown as Zone;
    
    // Clear cache
    await cacheService.clearPattern('zones:*');
    
    return savedZone;
  }

  async updateZone(id: string, data: any): Promise<Zone> {
    const zone = await this.zoneRepository.findOne({ where: { id } });

    if (!zone) {
      throw new ApiError(404, 'Zone not found');
    }

    Object.assign(zone, data);
    zone.updatedAt = new Date();

    const updatedZone = await this.zoneRepository.save(zone);

    // Clear cache
    await cacheService.delete(`zone:${id}`);
    await cacheService.clearPattern('zones:*');

    return updatedZone;
  }

  async updateZoneGeometry(id: string, geometry: Polygon): Promise<Zone> {
    const zone = await this.zoneRepository.findOne({ where: { id } });

    if (!zone) {
      throw new ApiError(404, 'Zone not found');
    }

    zone.geometry = geometry;
    zone.area = turf.area(geometry) / 10000; // Convert to hectares
    zone.updatedAt = new Date();

    const updatedZone = await this.zoneRepository.save(zone);

    // Clear cache
    await cacheService.delete(`zone:${id}`);
    await cacheService.clearPattern('zones:*');
    await cacheService.clearPattern('tile:zones:*');

    return updatedZone;
  }

  async deleteZone(id: string): Promise<void> {
    const zone = await this.zoneRepository.findOne({ where: { id } });

    if (!zone) {
      throw new ApiError(404, 'Zone not found');
    }

    // Check if zone has parcels
    const parcelCount = await this.parcelRepository.count({
      where: { zone: { id } },
    });

    if (parcelCount > 0) {
      throw new ApiError(400, 'Cannot delete zone with existing parcels');
    }

    await this.zoneRepository.remove(zone);

    // Clear cache
    await cacheService.delete(`zone:${id}`);
    await cacheService.clearPattern('zones:*');
    await cacheService.clearPattern('tile:zones:*');
  }

  async bulkImportZones(data: any, format: string): Promise<any> {
    let features: Feature[];

    if (format === 'geojson') {
      const featureCollection = data as FeatureCollection;
      features = featureCollection.features;
    } else {
      throw new ApiError(400, 'Unsupported format');
    }

    const zones: Zone[] = [];
    const errors: any[] = [];

    for (const feature of features) {
      try {
        const zone = this.zoneRepository.create({
          code: feature.properties?.code || `ZONE_${Date.now()}`,
          name: feature.properties?.name || 'Unnamed Zone',
          nameTh: feature.properties?.nameTh,
          type: feature.properties?.type || ZoneType.IRRIGATION,
          status: ZoneStatus.ACTIVE,
          geometry: feature.geometry as Polygon,
          area: turf.area(feature),
          perimeter: 0, // TODO: Calculate perimeter
          irrigableArea: feature.properties?.irrigableArea || 0,
          cultivatedArea: feature.properties?.cultivatedArea || 0,
          maxWaterAllocation: feature.properties?.waterAllocation || 0,
          statistics: {
            totalParcels: 0,
            waterUsage: {
              irrigatedArea: 0,
            },
          },
          createdAt: new Date(),
          updatedAt: new Date(),
        });

        zones.push(zone);
      } catch (error: any) {
        errors.push({
          feature: feature.properties?.code || 'unknown',
          error: error.message,
        });
      }
    }

    const savedZones = await this.zoneRepository.save(zones);

    // Clear cache
    await cacheService.clearPattern('zones:*');
    await cacheService.clearPattern('tile:zones:*');

    return {
      imported: savedZones.length,
      errors: errors.length,
      errorDetails: errors,
    };
  }

  async bulkUpdateZones(zones: any[]): Promise<any> {
    const updates: Zone[] = [];
    const errors: any[] = [];

    for (const zoneData of zones) {
      try {
        const zone = await this.zoneRepository.findOne({
          where: { id: zoneData.id },
        });

        if (!zone) {
          errors.push({
            id: zoneData.id,
            error: 'Zone not found',
          });
          continue;
        }

        Object.assign(zone, zoneData);
        zone.updatedAt = new Date();
        updates.push(zone);
      } catch (error: any) {
        errors.push({
          id: zoneData.id,
          error: error.message,
        });
      }
    }

    const savedZones = await this.zoneRepository.save(updates);

    // Clear cache
    await cacheService.clearPattern('zones:*');
    await cacheService.clearPattern('zone:*');
    await cacheService.clearPattern('tile:zones:*');

    return {
      updated: savedZones.length,
      errors: errors.length,
      errorDetails: errors,
    };
  }
}

export const zoneService = new ZoneService();