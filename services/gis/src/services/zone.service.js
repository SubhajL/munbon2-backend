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
exports.zoneService = void 0;
const database_1 = require("../config/database");
const zone_entity_1 = require("../models/zone.entity");
const parcel_entity_1 = require("../models/parcel.entity");
const api_error_1 = require("../utils/api-error");
const cache_service_1 = require("./cache.service");
const turf = __importStar(require("@turf/turf"));
class ZoneService {
    zoneRepository;
    parcelRepository;
    constructor() {
        this.zoneRepository = database_1.AppDataSource.getRepository(zone_entity_1.Zone);
        this.parcelRepository = database_1.AppDataSource.getRepository(parcel_entity_1.Parcel);
    }
    async getAllZones(query) {
        const { page, limit, includeGeometry } = query;
        const skip = (page - 1) * limit;
        const cacheKey = `zones:all:${page}:${limit}:${includeGeometry}`;
        const cached = await cache_service_1.cacheService.get(cacheKey);
        if (cached)
            return cached;
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
        await cache_service_1.cacheService.set(cacheKey, result, 300);
        return result;
    }
    async getZoneById(id) {
        const cacheKey = `zone:${id}`;
        const cached = await cache_service_1.cacheService.get(cacheKey);
        if (cached)
            return cached;
        const zone = await this.zoneRepository.findOne({
            where: { id },
            relations: ['canals', 'gates'],
        });
        if (zone) {
            await cache_service_1.cacheService.set(cacheKey, zone, 600);
        }
        return zone;
    }
    async queryZones(query) {
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
            queryBuilder.andWhere('ST_Intersects(zone.geometry, ST_MakeEnvelope(:minLng, :minLat, :maxLng, :maxLat, 4326))', { minLng, minLat, maxLng, maxLat });
        }
        if (query.nearPoint) {
            const { lng, lat, distance } = query.nearPoint;
            queryBuilder.andWhere('ST_DWithin(zone.geometry, ST_SetSRID(ST_Point(:lng, :lat), 4326), :distance)', { lng, lat, distance });
        }
        return queryBuilder.getMany();
    }
    async getZoneStatistics(zoneId) {
        const cacheKey = `zone:stats:${zoneId}`;
        const cached = await cache_service_1.cacheService.get(cacheKey);
        if (cached)
            return cached;
        const zone = await this.zoneRepository.findOne({
            where: { id: zoneId },
        });
        if (!zone) {
            throw new api_error_1.ApiError(404, 'Zone not found');
        }
        const parcels = await this.parcelRepository
            .createQueryBuilder('parcel')
            .where('parcel.zoneId = :zoneId', { zoneId })
            .getMany();
        const cropTypes = {};
        let irrigatedArea = 0;
        let nonIrrigatedArea = 0;
        parcels.forEach(parcel => {
            if (parcel.landUseType) {
                cropTypes[parcel.landUseType] = (cropTypes[parcel.landUseType] || 0) + parcel.area;
            }
            if (parcel.hasWaterAccess) {
                irrigatedArea += parcel.area;
            }
            else {
                nonIrrigatedArea += parcel.area;
            }
        });
        const waterUsage = {
            current: irrigatedArea * 0.7,
            allocated: zone.maxWaterAllocation || 0,
            percentage: zone.maxWaterAllocation ? (irrigatedArea * 0.7 / zone.maxWaterAllocation) * 100 : 0,
        };
        const stats = {
            totalArea: zone.area,
            totalParcels: zone.statistics?.totalParcels || parcels.length,
            irrigatedArea,
            nonIrrigatedArea,
            cropTypes,
            waterUsage,
        };
        await cache_service_1.cacheService.set(cacheKey, stats, 1800);
        return stats;
    }
    async getParcelsInZone(zoneId, options) {
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
    async getWaterDistribution(zoneId, dateRange) {
        return {
            zoneId,
            dateRange,
            totalAllocated: 1000000,
            totalUsed: 750000,
            distribution: [
                { date: '2024-01-01', allocated: 50000, used: 38000 },
                { date: '2024-01-02', allocated: 50000, used: 42000 },
            ],
        };
    }
    async createZone(data) {
        const zone = this.zoneRepository.create({
            ...data,
            createdAt: new Date(),
            updatedAt: new Date(),
        });
        if (data.geometry) {
            const area = turf.area(data.geometry);
            zone.area = area / 10000;
        }
        const savedZone = await this.zoneRepository.save(zone);
        await cache_service_1.cacheService.clearPattern('zones:*');
        return savedZone;
    }
    async updateZone(id, data) {
        const zone = await this.zoneRepository.findOne({ where: { id } });
        if (!zone) {
            throw new api_error_1.ApiError(404, 'Zone not found');
        }
        Object.assign(zone, data);
        zone.updatedAt = new Date();
        const updatedZone = await this.zoneRepository.save(zone);
        await cache_service_1.cacheService.delete(`zone:${id}`);
        await cache_service_1.cacheService.clearPattern('zones:*');
        return updatedZone;
    }
    async updateZoneGeometry(id, geometry) {
        const zone = await this.zoneRepository.findOne({ where: { id } });
        if (!zone) {
            throw new api_error_1.ApiError(404, 'Zone not found');
        }
        zone.geometry = geometry;
        zone.area = turf.area(geometry) / 10000;
        zone.updatedAt = new Date();
        const updatedZone = await this.zoneRepository.save(zone);
        await cache_service_1.cacheService.delete(`zone:${id}`);
        await cache_service_1.cacheService.clearPattern('zones:*');
        await cache_service_1.cacheService.clearPattern('tile:zones:*');
        return updatedZone;
    }
    async deleteZone(id) {
        const zone = await this.zoneRepository.findOne({ where: { id } });
        if (!zone) {
            throw new api_error_1.ApiError(404, 'Zone not found');
        }
        const parcelCount = await this.parcelRepository.count({
            where: { zone: { id } },
        });
        if (parcelCount > 0) {
            throw new api_error_1.ApiError(400, 'Cannot delete zone with existing parcels');
        }
        await this.zoneRepository.remove(zone);
        await cache_service_1.cacheService.delete(`zone:${id}`);
        await cache_service_1.cacheService.clearPattern('zones:*');
        await cache_service_1.cacheService.clearPattern('tile:zones:*');
    }
    async bulkImportZones(data, format) {
        let features;
        if (format === 'geojson') {
            const featureCollection = data;
            features = featureCollection.features;
        }
        else {
            throw new api_error_1.ApiError(400, 'Unsupported format');
        }
        const zones = [];
        const errors = [];
        for (const feature of features) {
            try {
                const zone = this.zoneRepository.create({
                    code: feature.properties?.code || `ZONE_${Date.now()}`,
                    name: feature.properties?.name || 'Unnamed Zone',
                    nameTh: feature.properties?.nameTh,
                    type: feature.properties?.type || zone_entity_1.ZoneType.IRRIGATION,
                    status: zone_entity_1.ZoneStatus.ACTIVE,
                    geometry: feature.geometry,
                    area: turf.area(feature),
                    perimeter: 0,
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
            }
            catch (error) {
                errors.push({
                    feature: feature.properties?.code || 'unknown',
                    error: error.message,
                });
            }
        }
        const savedZones = await this.zoneRepository.save(zones);
        await cache_service_1.cacheService.clearPattern('zones:*');
        await cache_service_1.cacheService.clearPattern('tile:zones:*');
        return {
            imported: savedZones.length,
            errors: errors.length,
            errorDetails: errors,
        };
    }
    async bulkUpdateZones(zones) {
        const updates = [];
        const errors = [];
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
            }
            catch (error) {
                errors.push({
                    id: zoneData.id,
                    error: error.message,
                });
            }
        }
        const savedZones = await this.zoneRepository.save(updates);
        await cache_service_1.cacheService.clearPattern('zones:*');
        await cache_service_1.cacheService.clearPattern('zone:*');
        await cache_service_1.cacheService.clearPattern('tile:zones:*');
        return {
            updated: savedZones.length,
            errors: errors.length,
            errorDetails: errors,
        };
    }
}
exports.zoneService = new ZoneService();
//# sourceMappingURL=zone.service.js.map