import { Repository, DeepPartial } from 'typeorm';
import { AppDataSource } from '../config/database';
import { Parcel } from '../models/parcel.entity';
import { Zone } from '../models/zone.entity';
import { logger } from '../utils/logger';
import { ApiError } from '../utils/api-error';
import { cacheService } from './cache.service';
import { Feature, FeatureCollection, Polygon } from 'geojson';
import * as turf from '@turf/turf';

interface ParcelQuery {
  page: number;
  limit: number;
  includeGeometry?: boolean;
  filters?: {
    zoneId?: string;
    landUseType?: string;
    irrigationStatus?: string;
  };
}

interface CropPlan {
  parcelId: string;
  season: string;
  year: number;
  cropType: string;
  plantingDate: Date;
  expectedHarvestDate: Date;
  estimatedYield: number;
  waterRequirement: number;
  status: string;
}

class ParcelService {
  private parcelRepository: Repository<Parcel>;
  private zoneRepository: Repository<Zone>;

  constructor() {
    this.parcelRepository = AppDataSource.getRepository(Parcel);
    this.zoneRepository = AppDataSource.getRepository(Zone);
  }

  async getAllParcels(query: ParcelQuery): Promise<any> {
    const { page, limit, includeGeometry, filters } = query;
    const skip = (page - 1) * limit;

    const queryBuilder = this.parcelRepository
      .createQueryBuilder('parcel')
      .leftJoinAndSelect('parcel.zone', 'zone')
      .select([
        'parcel.id',
        'parcel.plotCode',
        'parcel.areaHectares',
        'parcel.currentCropType',
        'parcel.farmerId',
        'parcel.soilType',
        'zone.id',
        'zone.zoneName',
      ]);

    if (includeGeometry) {
      queryBuilder.addSelect('parcel.boundary');
    }

    // Apply filters
    if (filters?.zoneId) {
      queryBuilder.andWhere('parcel.zoneId = :zoneId', { zoneId: filters.zoneId });
    }
    if (filters?.landUseType) {
      queryBuilder.andWhere('parcel.currentCropType = :currentCropType', { 
        currentCropType: filters.landUseType 
      });
    }

    const [parcels, total] = await queryBuilder
      .skip(skip)
      .take(limit)
      .getManyAndCount();

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

  async getParcelById(id: string): Promise<Parcel | null> {
    const cacheKey = `parcel:${id}`;
    const cached = await cacheService.get(cacheKey);
    if (cached) return cached;

    const parcel = await this.parcelRepository.findOne({
      where: { id },
      relations: ['zone'],
    });

    if (parcel) {
      await cacheService.set(cacheKey, parcel, 600); // 10 minutes
    }

    return parcel;
  }

  async queryParcels(query: any): Promise<Parcel[]> {
    const queryBuilder = this.parcelRepository.createQueryBuilder('parcel');

    if (query.zoneId) {
      queryBuilder.andWhere('parcel.zoneId = :zoneId', { zoneId: query.zoneId });
    }

    if (query.landUseType) {
      queryBuilder.andWhere('parcel.landUseType = :landUseType', { 
        landUseType: query.landUseType 
      });
    }

    if (query.irrigationStatus) {
      queryBuilder.andWhere('parcel.irrigationStatus = :irrigationStatus', { 
        irrigationStatus: query.irrigationStatus 
      });
    }

    if (query.ownerName) {
      queryBuilder.andWhere('LOWER(parcel.ownerName) LIKE LOWER(:ownerName)', { 
        ownerName: `%${query.ownerName}%` 
      });
    }

    if (query.minArea) {
      queryBuilder.andWhere('parcel.area >= :minArea', { minArea: query.minArea });
    }

    if (query.maxArea) {
      queryBuilder.andWhere('parcel.area <= :maxArea', { maxArea: query.maxArea });
    }

    if (query.bounds) {
      const [minLng, minLat, maxLng, maxLat] = query.bounds;
      queryBuilder.andWhere(
        'ST_Intersects(parcel.geometry, ST_MakeEnvelope(:minLng, :minLat, :maxLng, :maxLat, 4326))',
        { minLng, minLat, maxLng, maxLat }
      );
    }

    return queryBuilder.getMany();
  }

  async getParcelHistory(parcelId: string, dateRange: any): Promise<any> {
    // This would integrate with historical data tracking
    // For now, return mock data
    return {
      parcelId,
      history: [
        {
          date: '2024-01-01',
          event: 'Ownership Transfer',
          details: 'Transferred from John Doe to Jane Smith',
        },
        {
          date: '2023-06-15',
          event: 'Land Use Change',
          details: 'Changed from Rice to Mixed Crops',
        },
      ],
    };
  }

  async getParcelsByOwner(ownerId: string, options: any): Promise<any> {
    const { page, limit } = options;
    const skip = (page - 1) * limit;

    const [parcels, total] = await this.parcelRepository.findAndCount({
      where: { ownerName: ownerId }, // In production, this would use proper owner ID
      skip,
      take: limit,
      relations: ['zone'],
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

  async getCropPlan(parcelId: string, options: any): Promise<CropPlan | null> {
    // This would integrate with crop management service
    // For now, return mock data
    const parcel = await this.getParcelById(parcelId);
    if (!parcel) {
      throw new ApiError(404, 'Parcel not found');
    }

    return {
      parcelId,
      season: options.season || 'wet',
      year: options.year,
      cropType: 'Rice',
      plantingDate: new Date('2024-05-01'),
      expectedHarvestDate: new Date('2024-09-01'),
      estimatedYield: 5000, // kg
      waterRequirement: 12000, // cubic meters
      status: 'planned',
    };
  }

  async updateCropPlan(parcelId: string, planData: any): Promise<CropPlan> {
    const parcel = await this.getParcelById(parcelId);
    if (!parcel) {
      throw new ApiError(404, 'Parcel not found');
    }

    // This would update crop plan in crop management service
    return {
      parcelId,
      ...planData,
      status: 'active',
    };
  }

  async createParcel(data: any): Promise<Parcel> {
    // Verify zone exists
    const zone = await this.zoneRepository.findOne({
      where: { id: data.zoneId },
    });

    if (!zone) {
      throw new ApiError(400, 'Invalid zone ID');
    }

    const parcel: Parcel = this.parcelRepository.create({
      ...data,
      zone,
      createdAt: new Date(),
      updatedAt: new Date(),
    });

    // Calculate area if geometry provided
    if (data.geometry) {
      const area = turf.area(data.geometry);
      parcel.area = area / 10000; // Convert to hectares
    }

    const savedParcel = await this.parcelRepository.save(parcel as DeepPartial<Parcel>) as unknown as Parcel;

    // Update zone statistics
    await this.updateZoneStatistics(zone.id);

    // Clear cache
    await cacheService.clearPattern('parcels:*');
    await cacheService.clearPattern(`zone:${zone.id}`);

    return savedParcel;
  }

  async updateParcel(id: string, data: any): Promise<Parcel> {
    const parcel = await this.parcelRepository.findOne({
      where: { id },
      relations: ['zone'],
    });

    if (!parcel) {
      throw new ApiError(404, 'Parcel not found');
    }

    Object.assign(parcel, data);
    parcel.updatedAt = new Date();

    const updatedParcel = await this.parcelRepository.save(parcel);

    // Clear cache
    await cacheService.delete(`parcel:${id}`);
    await cacheService.clearPattern('parcels:*');

    return updatedParcel;
  }

  async updateParcelGeometry(id: string, geometry: Polygon): Promise<Parcel> {
    const parcel = await this.parcelRepository.findOne({
      where: { id },
      relations: ['zone'],
    });

    if (!parcel) {
      throw new ApiError(404, 'Parcel not found');
    }

    parcel.geometry = geometry;
    parcel.area = turf.area(geometry) / 10000; // Convert to hectares
    parcel.updatedAt = new Date();

    const updatedParcel = await this.parcelRepository.save(parcel);

    // Update zone statistics
    if (parcel.zone) {
      await this.updateZoneStatistics(parcel.zone.id);
    }

    // Clear cache
    await cacheService.delete(`parcel:${id}`);
    await cacheService.clearPattern('parcels:*');
    await cacheService.clearPattern('tile:parcels:*');

    return updatedParcel;
  }

  async transferOwnership(id: string, transferData: any): Promise<any> {
    const parcel = await this.parcelRepository.findOne({
      where: { id },
    });

    if (!parcel) {
      throw new ApiError(404, 'Parcel not found');
    }

    // Record the transfer (would integrate with user management service)
    const previousOwner = parcel.ownerName;
    parcel.ownerName = transferData.newOwnerId; // In production, use proper owner reference
    parcel.updatedAt = new Date();

    await this.parcelRepository.save(parcel);

    // Clear cache
    await cacheService.delete(`parcel:${id}`);
    await cacheService.clearPattern('parcels:*');

    return {
      parcelId: id,
      previousOwner,
      newOwner: transferData.newOwnerId,
      transferDate: transferData.transferDate,
      notes: transferData.notes,
    };
  }

  async deleteParcel(id: string): Promise<void> {
    const parcel = await this.parcelRepository.findOne({
      where: { id },
      relations: ['zone'],
    });

    if (!parcel) {
      throw new ApiError(404, 'Parcel not found');
    }

    const zoneId = parcel.zone?.id;
    await this.parcelRepository.remove(parcel);

    // Update zone statistics
    if (zoneId) {
      await this.updateZoneStatistics(zoneId);
    }

    // Clear cache
    await cacheService.delete(`parcel:${id}`);
    await cacheService.clearPattern('parcels:*');
    await cacheService.clearPattern('tile:parcels:*');
  }

  async bulkImportParcels(data: any, options: any): Promise<any> {
    let features: Feature[];

    if (options.format === 'geojson') {
      const featureCollection = data as FeatureCollection;
      features = featureCollection.features;
    } else {
      throw new ApiError(400, 'Unsupported format');
    }

    const zone = options.zoneId ? await this.zoneRepository.findOne({
      where: { id: options.zoneId },
    }) : null;

    const parcels: Parcel[] = [];
    const errors: any[] = [];

    for (const feature of features) {
      try {
        const parcel = this.parcelRepository.create({
          parcelCode: feature.properties?.parcelCode || `PARCEL_${Date.now()}`,
          area: turf.area(feature) / 10000,
          geometry: feature.geometry as Polygon,
          zoneId: zone?.id || feature.properties?.zoneId || 'default-zone',
          landUseType: feature.properties?.landUseType || 'unknown',
          soilType: feature.properties?.soilType,
          ownerName: feature.properties?.ownerName || 'Unknown',
          ownerId: feature.properties?.ownerId || 'unknown',
          ownerContact: feature.properties?.ownerContact,
          hasWaterAccess: feature.properties?.hasWaterAccess ?? true,
          waterAllocation: feature.properties?.waterRights || feature.properties?.waterAllocation || 0,
          createdAt: new Date(),
          updatedAt: new Date(),
        });

        parcels.push(parcel);
      } catch (error: any) {
        errors.push({
          feature: feature.properties?.parcelCode || 'unknown',
          error: error.message,
        });
      }
    }

    const savedParcels = await this.parcelRepository.save(parcels);

    // Update zone statistics
    if (zone) {
      await this.updateZoneStatistics(zone.id);
    }

    // Clear cache
    await cacheService.clearPattern('parcels:*');
    await cacheService.clearPattern('tile:parcels:*');

    return {
      imported: savedParcels.length,
      errors: errors.length,
      errorDetails: errors,
    };
  }

  async bulkUpdateParcels(parcels: any[]): Promise<any> {
    const updates: Parcel[] = [];
    const errors: any[] = [];

    for (const parcelData of parcels) {
      try {
        const parcel = await this.parcelRepository.findOne({
          where: { id: parcelData.id },
        });

        if (!parcel) {
          errors.push({
            id: parcelData.id,
            error: 'Parcel not found',
          });
          continue;
        }

        Object.assign(parcel, parcelData);
        parcel.updatedAt = new Date();
        updates.push(parcel);
      } catch (error: any) {
        errors.push({
          id: parcelData.id,
          error: error.message,
        });
      }
    }

    const savedParcels = await this.parcelRepository.save(updates);

    // Clear cache
    await cacheService.clearPattern('parcels:*');
    await cacheService.clearPattern('parcel:*');
    await cacheService.clearPattern('tile:parcels:*');

    return {
      updated: savedParcels.length,
      errors: errors.length,
      errorDetails: errors,
    };
  }

  async mergeParcels(parcelIds: string[], newParcelData: any): Promise<Parcel> {
    const parcels = await this.parcelRepository.findByIds(parcelIds);

    if (parcels.length !== parcelIds.length) {
      throw new ApiError(400, 'One or more parcels not found');
    }

    // Ensure all parcels are in the same zone
    const zoneIds = new Set(parcels.map(p => p.zone?.id));
    if (zoneIds.size > 1) {
      throw new ApiError(400, 'All parcels must be in the same zone');
    }

    // Create union of geometries
    const geometries = parcels.map(p => p.geometry);
    const features = geometries.map(g => turf.feature(g));
    
    // Union all geometries iteratively
    let merged = features[0];
    for (let i = 1; i < features.length; i++) {
      const union = turf.union(merged as any, features[i] as any);
      if (union) {
        merged = union;
      }
    }

    if (!merged) {
      throw new ApiError(400, 'Failed to merge parcel geometries');
    }

    // Create new parcel
    const newParcel = this.parcelRepository.create({
      ...newParcelData,
      geometry: merged.geometry as Polygon,
      area: turf.area(merged) / 10000,
      zone: parcels[0].zone,
      createdAt: new Date(),
      updatedAt: new Date(),
    });

    // Save new parcel
    const savedParcel = await this.parcelRepository.save(newParcel as DeepPartial<Parcel>) as unknown as Parcel;

    // Delete old parcels
    await this.parcelRepository.remove(parcels);

    // Update zone statistics
    if (parcels[0].zone) {
      await this.updateZoneStatistics(parcels[0].zone.id);
    }

    // Clear cache
    await cacheService.clearPattern('parcels:*');
    await cacheService.clearPattern('tile:parcels:*');

    return savedParcel;
  }

  async splitParcel(id: string, splitData: any): Promise<Parcel[]> {
    const parcel = await this.parcelRepository.findOne({
      where: { id },
      relations: ['zone'],
    });

    if (!parcel) {
      throw new ApiError(404, 'Parcel not found');
    }

    const { splitGeometries, splitData: newParcelsData } = splitData;

    // Validate split geometries
    const totalArea = splitGeometries.reduce((sum: number, geom: any) => {
      return sum + turf.area(geom) / 10000;
    }, 0);

    if (Math.abs(totalArea - parcel.area) > 0.01) {
      throw new ApiError(400, 'Split geometries area does not match original parcel area');
    }

    // Create new parcels
    const newParcels: Parcel[] = [];
    for (let i = 0; i < splitGeometries.length; i++) {
      const newParcel = this.parcelRepository.create({
        ...newParcelsData[i],
        geometry: splitGeometries[i],
        area: turf.area(splitGeometries[i]) / 10000,
        zone: parcel.zone,
        createdAt: new Date(),
        updatedAt: new Date(),
      });
      newParcels.push(newParcel);
    }

    // Save new parcels
    const savedParcels = await this.parcelRepository.save(newParcels);

    // Delete original parcel
    await this.parcelRepository.remove(parcel);

    // Update zone statistics
    if (parcel.zone) {
      await this.updateZoneStatistics(parcel.zone.id);
    }

    // Clear cache
    await cacheService.clearPattern('parcels:*');
    await cacheService.clearPattern('tile:parcels:*');

    return savedParcels;
  }

  private async updateZoneStatistics(zoneId: string): Promise<void> {
    const stats = await this.parcelRepository
      .createQueryBuilder('parcel')
      .where('parcel.zoneId = :zoneId', { zoneId })
      .select('COUNT(*)', 'count')
      .addSelect('SUM(parcel.area)', 'totalArea')
      .addSelect('SUM(CASE WHEN parcel.hasWaterAccess = true THEN parcel.area ELSE 0 END)', 'irrigatedArea')
      .getRawOne();

    const zone = await this.zoneRepository.findOne({ where: { id: zoneId } });
    if (!zone) return;

    await this.zoneRepository.update(zoneId, {
      area: parseFloat(stats.totalArea) || 0,
      irrigableArea: parseFloat(stats.irrigatedArea) || 0,
      statistics: {
        ...(zone.statistics || {}),
        totalParcels: parseInt(stats.count) || 0,
        waterUsage: {
          ...(zone.statistics?.waterUsage || {}),
          irrigatedArea: parseFloat(stats.irrigatedArea) || 0,
        },
      },
      updatedAt: new Date(),
    });

    // Clear zone cache
    await cacheService.delete(`zone:${zoneId}`);
    await cacheService.clearPattern('zones:*');
  }
}

export const parcelService = new ParcelService();