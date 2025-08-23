"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.parcelService = void 0;
const database_1 = require("../config/database");
const parcel_entity_1 = require("../models/parcel.entity");
const zone_entity_1 = require("../models/zone.entity");
const api_error_1 = require("../utils/api-error");
const cache_service_1 = require("./cache.service");
const turf = __importStar(require("@turf/turf"));
class ParcelService {
    parcelRepository;
    zoneRepository;
    constructor() {
        this.parcelRepository = database_1.AppDataSource.getRepository(parcel_entity_1.Parcel);
        this.zoneRepository = database_1.AppDataSource.getRepository(zone_entity_1.Zone);
    }
    async getAllParcels(query) {
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
    async getParcelById(id) {
        const cacheKey = `parcel:${id}`;
        const cached = await cache_service_1.cacheService.get(cacheKey);
        if (cached)
            return cached;
        const parcel = await this.parcelRepository.findOne({
            where: { id },
            relations: ['zone'],
        });
        if (parcel) {
            await cache_service_1.cacheService.set(cacheKey, parcel, 600);
        }
        return parcel;
    }
    async queryParcels(query) {
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
            queryBuilder.andWhere('ST_Intersects(parcel.geometry, ST_MakeEnvelope(:minLng, :minLat, :maxLng, :maxLat, 4326))', { minLng, minLat, maxLng, maxLat });
        }
        return queryBuilder.getMany();
    }
    async getParcelHistory(parcelId, dateRange) {
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
    async getParcelsByOwner(ownerId, options) {
        const { page, limit } = options;
        const skip = (page - 1) * limit;
        const [parcels, total] = await this.parcelRepository.findAndCount({
            where: { ownerName: ownerId },
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
    async getCropPlan(parcelId, options) {
        const parcel = await this.getParcelById(parcelId);
        if (!parcel) {
            throw new api_error_1.ApiError(404, 'Parcel not found');
        }
        return {
            parcelId,
            season: options.season || 'wet',
            year: options.year,
            cropType: 'Rice',
            plantingDate: new Date('2024-05-01'),
            expectedHarvestDate: new Date('2024-09-01'),
            estimatedYield: 5000,
            waterRequirement: 12000,
            status: 'planned',
        };
    }
    async updateCropPlan(parcelId, planData) {
        const parcel = await this.getParcelById(parcelId);
        if (!parcel) {
            throw new api_error_1.ApiError(404, 'Parcel not found');
        }
        return {
            parcelId,
            ...planData,
            status: 'active',
        };
    }
    async createParcel(data) {
        const zone = await this.zoneRepository.findOne({
            where: { id: data.zoneId },
        });
        if (!zone) {
            throw new api_error_1.ApiError(400, 'Invalid zone ID');
        }
        const parcel = this.parcelRepository.create({
            ...data,
            zone,
            createdAt: new Date(),
            updatedAt: new Date(),
        });
        if (data.geometry) {
            const area = turf.area(data.geometry);
            parcel.area = area / 10000;
        }
        const savedParcel = await this.parcelRepository.save(parcel);
        await this.updateZoneStatistics(zone.id);
        await cache_service_1.cacheService.clearPattern('parcels:*');
        await cache_service_1.cacheService.clearPattern(`zone:${zone.id}`);
        return savedParcel;
    }
    async updateParcel(id, data) {
        const parcel = await this.parcelRepository.findOne({
            where: { id },
            relations: ['zone'],
        });
        if (!parcel) {
            throw new api_error_1.ApiError(404, 'Parcel not found');
        }
        Object.assign(parcel, data);
        parcel.updatedAt = new Date();
        const updatedParcel = await this.parcelRepository.save(parcel);
        await cache_service_1.cacheService.delete(`parcel:${id}`);
        await cache_service_1.cacheService.clearPattern('parcels:*');
        return updatedParcel;
    }
    async updateParcelGeometry(id, geometry) {
        const parcel = await this.parcelRepository.findOne({
            where: { id },
            relations: ['zone'],
        });
        if (!parcel) {
            throw new api_error_1.ApiError(404, 'Parcel not found');
        }
        parcel.geometry = geometry;
        parcel.area = turf.area(geometry) / 10000;
        parcel.updatedAt = new Date();
        const updatedParcel = await this.parcelRepository.save(parcel);
        if (parcel.zone) {
            await this.updateZoneStatistics(parcel.zone.id);
        }
        await cache_service_1.cacheService.delete(`parcel:${id}`);
        await cache_service_1.cacheService.clearPattern('parcels:*');
        await cache_service_1.cacheService.clearPattern('tile:parcels:*');
        return updatedParcel;
    }
    async transferOwnership(id, transferData) {
        const parcel = await this.parcelRepository.findOne({
            where: { id },
        });
        if (!parcel) {
            throw new api_error_1.ApiError(404, 'Parcel not found');
        }
        const previousOwner = parcel.ownerName;
        parcel.ownerName = transferData.newOwnerId;
        parcel.updatedAt = new Date();
        await this.parcelRepository.save(parcel);
        await cache_service_1.cacheService.delete(`parcel:${id}`);
        await cache_service_1.cacheService.clearPattern('parcels:*');
        return {
            parcelId: id,
            previousOwner,
            newOwner: transferData.newOwnerId,
            transferDate: transferData.transferDate,
            notes: transferData.notes,
        };
    }
    async deleteParcel(id) {
        const parcel = await this.parcelRepository.findOne({
            where: { id },
            relations: ['zone'],
        });
        if (!parcel) {
            throw new api_error_1.ApiError(404, 'Parcel not found');
        }
        const zoneId = parcel.zone?.id;
        await this.parcelRepository.remove(parcel);
        if (zoneId) {
            await this.updateZoneStatistics(zoneId);
        }
        await cache_service_1.cacheService.delete(`parcel:${id}`);
        await cache_service_1.cacheService.clearPattern('parcels:*');
        await cache_service_1.cacheService.clearPattern('tile:parcels:*');
    }
    async bulkImportParcels(data, options) {
        let features;
        if (options.format === 'geojson') {
            const featureCollection = data;
            features = featureCollection.features;
        }
        else {
            throw new api_error_1.ApiError(400, 'Unsupported format');
        }
        const zone = options.zoneId ? await this.zoneRepository.findOne({
            where: { id: options.zoneId },
        }) : null;
        const parcels = [];
        const errors = [];
        for (const feature of features) {
            try {
                const parcel = this.parcelRepository.create({
                    parcelCode: feature.properties?.parcelCode || `PARCEL_${Date.now()}`,
                    area: turf.area(feature) / 10000,
                    geometry: feature.geometry,
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
            }
            catch (error) {
                errors.push({
                    feature: feature.properties?.parcelCode || 'unknown',
                    error: error.message,
                });
            }
        }
        const savedParcels = await this.parcelRepository.save(parcels);
        if (zone) {
            await this.updateZoneStatistics(zone.id);
        }
        await cache_service_1.cacheService.clearPattern('parcels:*');
        await cache_service_1.cacheService.clearPattern('tile:parcels:*');
        return {
            imported: savedParcels.length,
            errors: errors.length,
            errorDetails: errors,
        };
    }
    async bulkUpdateParcels(parcels) {
        const updates = [];
        const errors = [];
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
            }
            catch (error) {
                errors.push({
                    id: parcelData.id,
                    error: error.message,
                });
            }
        }
        const savedParcels = await this.parcelRepository.save(updates);
        await cache_service_1.cacheService.clearPattern('parcels:*');
        await cache_service_1.cacheService.clearPattern('parcel:*');
        await cache_service_1.cacheService.clearPattern('tile:parcels:*');
        return {
            updated: savedParcels.length,
            errors: errors.length,
            errorDetails: errors,
        };
    }
    async mergeParcels(parcelIds, newParcelData) {
        const parcels = await this.parcelRepository.findByIds(parcelIds);
        if (parcels.length !== parcelIds.length) {
            throw new api_error_1.ApiError(400, 'One or more parcels not found');
        }
        const zoneIds = new Set(parcels.map(p => p.zone?.id));
        if (zoneIds.size > 1) {
            throw new api_error_1.ApiError(400, 'All parcels must be in the same zone');
        }
        const geometries = parcels.map(p => p.geometry);
        const features = geometries.map(g => turf.feature(g));
        let merged = features[0];
        for (let i = 1; i < features.length; i++) {
            const union = turf.union(merged, features[i]);
            if (union) {
                merged = union;
            }
        }
        if (!merged) {
            throw new api_error_1.ApiError(400, 'Failed to merge parcel geometries');
        }
        const newParcel = this.parcelRepository.create({
            ...newParcelData,
            geometry: merged.geometry,
            area: turf.area(merged) / 10000,
            zone: parcels[0].zone,
            createdAt: new Date(),
            updatedAt: new Date(),
        });
        const savedParcel = await this.parcelRepository.save(newParcel);
        await this.parcelRepository.remove(parcels);
        if (parcels[0].zone) {
            await this.updateZoneStatistics(parcels[0].zone.id);
        }
        await cache_service_1.cacheService.clearPattern('parcels:*');
        await cache_service_1.cacheService.clearPattern('tile:parcels:*');
        return savedParcel;
    }
    async splitParcel(id, splitData) {
        const parcel = await this.parcelRepository.findOne({
            where: { id },
            relations: ['zone'],
        });
        if (!parcel) {
            throw new api_error_1.ApiError(404, 'Parcel not found');
        }
        const { splitGeometries, splitData: newParcelsData } = splitData;
        const totalArea = splitGeometries.reduce((sum, geom) => {
            return sum + turf.area(geom) / 10000;
        }, 0);
        if (Math.abs(totalArea - parcel.area) > 0.01) {
            throw new api_error_1.ApiError(400, 'Split geometries area does not match original parcel area');
        }
        const newParcels = [];
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
        const savedParcels = await this.parcelRepository.save(newParcels);
        await this.parcelRepository.remove(parcel);
        if (parcel.zone) {
            await this.updateZoneStatistics(parcel.zone.id);
        }
        await cache_service_1.cacheService.clearPattern('parcels:*');
        await cache_service_1.cacheService.clearPattern('tile:parcels:*');
        return savedParcels;
    }
    async updateZoneStatistics(zoneId) {
        const stats = await this.parcelRepository
            .createQueryBuilder('parcel')
            .where('parcel.zoneId = :zoneId', { zoneId })
            .select('COUNT(*)', 'count')
            .addSelect('SUM(parcel.area)', 'totalArea')
            .addSelect('SUM(CASE WHEN parcel.hasWaterAccess = true THEN parcel.area ELSE 0 END)', 'irrigatedArea')
            .getRawOne();
        const zone = await this.zoneRepository.findOne({ where: { id: zoneId } });
        if (!zone)
            return;
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
        await cache_service_1.cacheService.delete(`zone:${zoneId}`);
        await cache_service_1.cacheService.clearPattern('zones:*');
    }
}
exports.parcelService = new ParcelService();
//# sourceMappingURL=parcel.service.js.map