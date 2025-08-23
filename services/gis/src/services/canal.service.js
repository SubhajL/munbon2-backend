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
exports.canalService = void 0;
const database_1 = require("../config/database");
const canal_entity_1 = require("../models/canal.entity");
const gate_entity_1 = require("../models/gate.entity");
const logger_1 = require("../utils/logger");
const api_error_1 = require("../utils/api-error");
const cache_service_1 = require("./cache.service");
const turf = __importStar(require("@turf/turf"));
class CanalService {
    canalRepository;
    gateRepository;
    constructor() {
        this.canalRepository = database_1.AppDataSource.getRepository(canal_entity_1.Canal);
        this.gateRepository = database_1.AppDataSource.getRepository(gate_entity_1.Gate);
    }
    async getAllCanals(query) {
        const { page, limit, includeGeometry, filters } = query;
        const skip = (page - 1) * limit;
        const queryBuilder = this.canalRepository
            .createQueryBuilder('canal')
            .select([
            'canal.id',
            'canal.code',
            'canal.name',
            'canal.type',
            'canal.level',
            'canal.length',
            'canal.capacity',
            'canal.status',
            'canal.currentFlow',
        ]);
        if (includeGeometry) {
            queryBuilder.addSelect('canal.geometry');
        }
        if (filters?.type) {
            queryBuilder.andWhere('canal.type = :type', { type: filters.type });
        }
        if (filters?.status) {
            queryBuilder.andWhere('canal.status = :status', { status: filters.status });
        }
        if (filters?.level) {
            queryBuilder.andWhere('canal.level = :level', { level: filters.level });
        }
        const [canals, total] = await queryBuilder
            .orderBy('canal.level', 'ASC')
            .addOrderBy('canal.code', 'ASC')
            .skip(skip)
            .take(limit)
            .getManyAndCount();
        return {
            canals,
            pagination: {
                page,
                limit,
                total,
                pages: Math.ceil(total / limit),
            },
        };
    }
    async getCanalById(id) {
        const cacheKey = `canal:${id}`;
        const cached = await cache_service_1.cacheService.get(cacheKey);
        if (cached)
            return cached;
        const canal = await this.canalRepository.findOne({
            where: { id },
            relations: ['gates'],
        });
        if (canal) {
            await cache_service_1.cacheService.set(cacheKey, canal, 600);
        }
        return canal;
    }
    async queryCanals(query) {
        const queryBuilder = this.canalRepository.createQueryBuilder('canal');
        if (query.type) {
            queryBuilder.andWhere('canal.type = :type', { type: query.type });
        }
        if (query.level) {
            queryBuilder.andWhere('canal.level = :level', { level: query.level });
        }
        if (query.status) {
            queryBuilder.andWhere('canal.status = :status', { status: query.status });
        }
        if (query.minCapacity) {
            queryBuilder.andWhere('canal.capacity >= :minCapacity', {
                minCapacity: query.minCapacity
            });
        }
        if (query.maxCapacity) {
            queryBuilder.andWhere('canal.capacity <= :maxCapacity', {
                maxCapacity: query.maxCapacity
            });
        }
        if (query.bounds) {
            const [minLng, minLat, maxLng, maxLat] = query.bounds;
            queryBuilder.andWhere('ST_Intersects(canal.geometry, ST_MakeEnvelope(:minLng, :minLat, :maxLng, :maxLat, 4326))', { minLng, minLat, maxLng, maxLat });
        }
        if (query.nearPoint) {
            const { lng, lat, distance } = query.nearPoint;
            queryBuilder.andWhere('ST_DWithin(canal.geometry, ST_SetSRID(ST_Point(:lng, :lat), 4326), :distance)', { lng, lat, distance });
        }
        return queryBuilder.getMany();
    }
    async getFlowHistory(canalId, options) {
        const { startDate, endDate, interval } = options;
        return [
            {
                timestamp: new Date('2024-01-01T08:00:00'),
                flowRate: 2.5,
                sensorId: 'SENSOR001',
            },
            {
                timestamp: new Date('2024-01-01T09:00:00'),
                flowRate: 2.8,
                sensorId: 'SENSOR001',
            },
            {
                timestamp: new Date('2024-01-01T10:00:00'),
                flowRate: 3.1,
                sensorId: 'SENSOR001',
            },
        ];
    }
    async getConnectedGates(canalId) {
        return this.gateRepository.find({
            where: { canal: { id: canalId } },
            select: ['id', 'code', 'name', 'type', 'status', 'openingWidth', 'openingHeight'],
        });
    }
    async getNetworkTopology(options) {
        const { startNodeId, depth } = options;
        const canals = await this.canalRepository.find({
            relations: ['gates'],
            take: 10,
        });
        const nodes = canals.map(canal => ({
            id: canal.id,
            type: 'canal',
            name: canal.name,
            connections: canal.gates?.map(g => g.id) || [],
            properties: {
                designCapacity: canal.designCapacity,
                currentCapacity: canal.currentCapacity,
                status: canal.status,
            },
        }));
        return nodes;
    }
    async updateCanalStatus(id, statusData) {
        const canal = await this.canalRepository.findOne({ where: { id } });
        if (!canal) {
            throw new api_error_1.ApiError(404, 'Canal not found');
        }
        canal.status = statusData.status;
        canal.updatedAt = new Date();
        const updatedCanal = await this.canalRepository.save(canal);
        logger_1.logger.info(`Canal ${canal.code} status changed to ${statusData.status}`, {
            canalId: id,
            reason: statusData.reason,
            updatedBy: statusData.updatedBy,
        });
        await cache_service_1.cacheService.delete(`canal:${id}`);
        await cache_service_1.cacheService.clearPattern('canals:*');
        return updatedCanal;
    }
    async updateFlowRate(id, flowData) {
        const canal = await this.canalRepository.findOne({ where: { id } });
        if (!canal) {
            throw new api_error_1.ApiError(404, 'Canal not found');
        }
        canal.updatedAt = new Date();
        await this.canalRepository.save(canal);
        await cache_service_1.cacheService.delete(`canal:${id}`);
        return {
            canalId: id,
            flowRate: flowData.flowRate,
            measuredAt: flowData.measuredAt,
            capacityUtilization: canal.designCapacity ? (flowData.flowRate / canal.designCapacity) * 100 : null,
        };
    }
    async getMaintenanceHistory(id, options) {
        const { page, limit } = options;
        return {
            maintenanceRecords: [
                {
                    id: 'MAINT001',
                    date: '2024-01-15',
                    type: 'cleaning',
                    description: 'Routine canal cleaning',
                    status: 'completed',
                    cost: 5000,
                },
                {
                    id: 'MAINT002',
                    date: '2023-11-20',
                    type: 'repair',
                    description: 'Concrete lining repair',
                    status: 'completed',
                    cost: 25000,
                },
            ],
            pagination: {
                page,
                limit,
                total: 2,
                pages: 1,
            },
        };
    }
    async createCanal(data) {
        const canal = this.canalRepository.create({
            ...data,
            createdAt: new Date(),
            updatedAt: new Date(),
        });
        if (data.geometry) {
            const length = turf.length(turf.feature(data.geometry), { units: 'meters' });
            canal.length = length;
        }
        const savedCanal = await this.canalRepository.save(canal);
        await cache_service_1.cacheService.clearPattern('canals:*');
        await cache_service_1.cacheService.clearPattern('tile:canals:*');
        return savedCanal;
    }
    async updateCanal(id, data) {
        const canal = await this.canalRepository.findOne({ where: { id } });
        if (!canal) {
            throw new api_error_1.ApiError(404, 'Canal not found');
        }
        Object.assign(canal, data);
        canal.updatedAt = new Date();
        const updatedCanal = await this.canalRepository.save(canal);
        await cache_service_1.cacheService.delete(`canal:${id}`);
        await cache_service_1.cacheService.clearPattern('canals:*');
        return updatedCanal;
    }
    async updateCanalGeometry(id, geometry) {
        const canal = await this.canalRepository.findOne({ where: { id } });
        if (!canal) {
            throw new api_error_1.ApiError(404, 'Canal not found');
        }
        canal.geometry = geometry;
        canal.length = turf.length(turf.feature(geometry), { units: 'meters' });
        canal.updatedAt = new Date();
        const updatedCanal = await this.canalRepository.save(canal);
        await cache_service_1.cacheService.delete(`canal:${id}`);
        await cache_service_1.cacheService.clearPattern('canals:*');
        await cache_service_1.cacheService.clearPattern('tile:canals:*');
        return updatedCanal;
    }
    async deleteCanal(id) {
        const canal = await this.canalRepository.findOne({
            where: { id },
            relations: ['gates'],
        });
        if (!canal) {
            throw new api_error_1.ApiError(404, 'Canal not found');
        }
        if (canal.gates && canal.gates.length > 0) {
            throw new api_error_1.ApiError(400, 'Cannot delete canal with connected gates');
        }
        await this.canalRepository.remove(canal);
        await cache_service_1.cacheService.delete(`canal:${id}`);
        await cache_service_1.cacheService.clearPattern('canals:*');
        await cache_service_1.cacheService.clearPattern('tile:canals:*');
    }
    async analyzeNetwork(analysisData) {
        const { sourceId, targetIds, analysisType } = analysisData;
        switch (analysisType) {
            case 'connectivity':
                return this.analyzeConnectivity(sourceId, targetIds);
            case 'flow_path':
                return this.analyzeFlowPath(sourceId, targetIds);
            case 'capacity':
                return this.analyzeCapacity(sourceId, targetIds);
            default:
                throw new api_error_1.ApiError(400, 'Invalid analysis type');
        }
    }
    async analyzeConnectivity(sourceId, targetIds) {
        return {
            source: sourceId,
            targets: targetIds,
            connected: targetIds.map(id => ({
                targetId: id,
                isConnected: true,
                pathLength: 3,
            })),
        };
    }
    async analyzeFlowPath(sourceId, targetIds) {
        return {
            source: sourceId,
            targets: targetIds,
            flowPaths: targetIds.map(id => ({
                targetId: id,
                path: [sourceId, 'CANAL_002', 'CANAL_003', id],
                totalLength: 5430,
                minCapacity: 3.5,
            })),
        };
    }
    async analyzeCapacity(sourceId, targetIds) {
        return {
            source: sourceId,
            targets: targetIds,
            capacityAnalysis: {
                totalDemand: 12.5,
                availableCapacity: 15.0,
                utilizationPercentage: 83.3,
                bottlenecks: [],
            },
        };
    }
    async optimizeFlow(optimizationData) {
        const { constraints, objectives } = optimizationData;
        return {
            status: 'optimal',
            objectives: {
                waterDistribution: 0.95,
                energyUsage: 0.85,
            },
            recommendations: [
                {
                    canalId: 'CANAL_001',
                    recommendedFlow: 3.2,
                    currentFlow: 2.8,
                    adjustment: 0.4,
                },
                {
                    canalId: 'CANAL_005',
                    recommendedFlow: 2.1,
                    currentFlow: 2.5,
                    adjustment: -0.4,
                },
            ],
            constraints: {
                satisfied: true,
                violations: [],
            },
        };
    }
    async identifyBottlenecks(options) {
        const { threshold, includeRecommendations } = options;
        const bottlenecks = [];
        const results = bottlenecks.map(canal => ({
            canalId: canal.id,
            code: canal.code,
            name: canal.name,
            utilizationPercentage: 0,
            severity: 'unknown',
            recommendations: includeRecommendations ? this.getBottleneckRecommendations(canal) : undefined,
        }));
        return results;
    }
    getBottleneckRecommendations(canal) {
        const recommendations = [];
        recommendations.push('Monitor canal conditions');
        recommendations.push('Schedule regular maintenance');
        if (canal.type === canal_entity_1.CanalType.SUB_LATERAL || canal.type === canal_entity_1.CanalType.FIELD) {
            recommendations.push('Implement rotation schedule for connected parcels');
        }
        return recommendations;
    }
    async bulkImportCanals(data, format) {
        let features;
        if (format === 'geojson') {
            const featureCollection = data;
            features = featureCollection.features;
        }
        else {
            throw new api_error_1.ApiError(400, 'Unsupported format');
        }
        const canals = [];
        const errors = [];
        for (const feature of features) {
            try {
                const canal = this.canalRepository.create({
                    code: feature.properties?.code || `CANAL_${Date.now()}`,
                    name: feature.properties?.name || 'Unnamed Canal',
                    type: feature.properties?.type || canal_entity_1.CanalType.SUB_LATERAL,
                    geometry: feature.geometry,
                    length: turf.length(feature, { units: 'meters' }),
                    width: feature.properties?.width,
                    depth: feature.properties?.depth,
                    designCapacity: feature.properties?.capacity || 1.0,
                    liningType: feature.properties?.material,
                    status: canal_entity_1.CanalStatus.OPERATIONAL,
                    zoneId: feature.properties?.zoneId || 'default-zone',
                    startPoint: {
                        lat: 0,
                        lng: 0,
                    },
                    endPoint: {
                        lat: 0,
                        lng: 0,
                    },
                    createdAt: new Date(),
                    updatedAt: new Date(),
                });
                canals.push(canal);
            }
            catch (error) {
                errors.push({
                    feature: feature.properties?.code || 'unknown',
                    error: error.message,
                });
            }
        }
        const savedCanals = await this.canalRepository.save(canals);
        await cache_service_1.cacheService.clearPattern('canals:*');
        await cache_service_1.cacheService.clearPattern('tile:canals:*');
        return {
            imported: savedCanals.length,
            errors: errors.length,
            errorDetails: errors,
        };
    }
    async bulkUpdateCanals(canals) {
        const updates = [];
        const errors = [];
        for (const canalData of canals) {
            try {
                const canal = await this.canalRepository.findOne({
                    where: { id: canalData.id },
                });
                if (!canal) {
                    errors.push({
                        id: canalData.id,
                        error: 'Canal not found',
                    });
                    continue;
                }
                Object.assign(canal, canalData);
                canal.updatedAt = new Date();
                updates.push(canal);
            }
            catch (error) {
                errors.push({
                    id: canalData.id,
                    error: error.message,
                });
            }
        }
        const savedCanals = await this.canalRepository.save(updates);
        await cache_service_1.cacheService.clearPattern('canals:*');
        await cache_service_1.cacheService.clearPattern('canal:*');
        await cache_service_1.cacheService.clearPattern('tile:canals:*');
        return {
            updated: savedCanals.length,
            errors: errors.length,
            errorDetails: errors,
        };
    }
}
exports.canalService = new CanalService();
//# sourceMappingURL=canal.service.js.map