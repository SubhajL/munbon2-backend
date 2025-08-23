import { Repository, DeepPartial } from 'typeorm';
import { AppDataSource } from '../config/database';
import { Canal, CanalType, CanalStatus } from '../models/canal.entity';
import { Gate } from '../models/gate.entity';
import { logger } from '../utils/logger';
import { ApiError } from '../utils/api-error';
import { cacheService } from './cache.service';
import { Feature, FeatureCollection, LineString } from 'geojson';
import * as turf from '@turf/turf';

interface CanalQuery {
  page: number;
  limit: number;
  includeGeometry?: boolean;
  filters?: {
    type?: string;
    status?: string;
    level?: number;
  };
}

interface FlowHistory {
  timestamp: Date;
  flowRate: number;
  sensorId?: string;
}

interface NetworkNode {
  id: string;
  type: 'canal' | 'gate' | 'pump' | 'junction';
  name: string;
  connections: string[];
  properties: any;
}

class CanalService {
  private canalRepository: Repository<Canal>;
  private gateRepository: Repository<Gate>;

  constructor() {
    this.canalRepository = AppDataSource.getRepository(Canal);
    this.gateRepository = AppDataSource.getRepository(Gate);
  }

  async getAllCanals(query: CanalQuery): Promise<any> {
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

    // Apply filters
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

  async getCanalById(id: string): Promise<Canal | null> {
    const cacheKey = `canal:${id}`;
    const cached = await cacheService.get(cacheKey);
    if (cached) return cached;

    const canal = await this.canalRepository.findOne({
      where: { id },
      relations: ['gates'],
    });

    if (canal) {
      await cacheService.set(cacheKey, canal, 600); // 10 minutes
    }

    return canal;
  }

  async queryCanals(query: any): Promise<Canal[]> {
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
      queryBuilder.andWhere(
        'ST_Intersects(canal.geometry, ST_MakeEnvelope(:minLng, :minLat, :maxLng, :maxLat, 4326))',
        { minLng, minLat, maxLng, maxLat }
      );
    }

    if (query.nearPoint) {
      const { lng, lat, distance } = query.nearPoint;
      queryBuilder.andWhere(
        'ST_DWithin(canal.geometry, ST_SetSRID(ST_Point(:lng, :lat), 4326), :distance)',
        { lng, lat, distance }
      );
    }

    return queryBuilder.getMany();
  }

  async getFlowHistory(canalId: string, options: any): Promise<FlowHistory[]> {
    // This would integrate with sensor data service
    // For now, return mock data
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

  async getConnectedGates(canalId: string): Promise<Gate[]> {
    return this.gateRepository.find({
      where: { canal: { id: canalId } },
      select: ['id', 'code', 'name', 'type', 'status', 'openingWidth', 'openingHeight'],
    });
  }

  async getNetworkTopology(options: any): Promise<NetworkNode[]> {
    // Build network topology from canals and gates
    const { startNodeId, depth } = options;
    
    // This would implement a graph traversal algorithm
    // For now, return simplified topology
    const canals = await this.canalRepository.find({
      relations: ['gates'],
      take: 10,
    });

    const nodes: NetworkNode[] = canals.map(canal => ({
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

  async updateCanalStatus(id: string, statusData: any): Promise<Canal> {
    const canal = await this.canalRepository.findOne({ where: { id } });

    if (!canal) {
      throw new ApiError(404, 'Canal not found');
    }

    canal.status = statusData.status;
    canal.updatedAt = new Date();

    const updatedCanal = await this.canalRepository.save(canal);

    // Log status change
    logger.info(`Canal ${canal.code} status changed to ${statusData.status}`, {
      canalId: id,
      reason: statusData.reason,
      updatedBy: statusData.updatedBy,
    });

    // Clear cache
    await cacheService.delete(`canal:${id}`);
    await cacheService.clearPattern('canals:*');

    return updatedCanal;
  }

  async updateFlowRate(id: string, flowData: any): Promise<any> {
    const canal = await this.canalRepository.findOne({ where: { id } });

    if (!canal) {
      throw new ApiError(404, 'Canal not found');
    }

    // TODO: Add flow tracking fields to Canal entity or create separate flow tracking table
    // canal.currentFlow = flowData.flowRate;
    // canal.lastFlowUpdate = new Date(flowData.measuredAt);
    canal.updatedAt = new Date();

    await this.canalRepository.save(canal);

    // Clear cache
    await cacheService.delete(`canal:${id}`);

    return {
      canalId: id,
      flowRate: flowData.flowRate,
      measuredAt: flowData.measuredAt,
      capacityUtilization: canal.designCapacity ? (flowData.flowRate / canal.designCapacity) * 100 : null,
    };
  }

  async getMaintenanceHistory(id: string, options: any): Promise<any> {
    // This would integrate with maintenance service
    // For now, return mock data
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

  async createCanal(data: any): Promise<Canal> {
    const canal = this.canalRepository.create({
      ...data,
      createdAt: new Date(),
      updatedAt: new Date(),
    });

    // Calculate length if geometry provided
    if (data.geometry) {
      const length = turf.length(turf.feature(data.geometry), { units: 'meters' });
      canal.length = length;
    }

    const savedCanal = await this.canalRepository.save(canal as DeepPartial<Canal>) as unknown as Canal;

    // Clear cache
    await cacheService.clearPattern('canals:*');
    await cacheService.clearPattern('tile:canals:*');

    return savedCanal;
  }

  async updateCanal(id: string, data: any): Promise<Canal> {
    const canal = await this.canalRepository.findOne({ where: { id } });

    if (!canal) {
      throw new ApiError(404, 'Canal not found');
    }

    Object.assign(canal, data);
    canal.updatedAt = new Date();

    const updatedCanal = await this.canalRepository.save(canal);

    // Clear cache
    await cacheService.delete(`canal:${id}`);
    await cacheService.clearPattern('canals:*');

    return updatedCanal;
  }

  async updateCanalGeometry(id: string, geometry: LineString): Promise<Canal> {
    const canal = await this.canalRepository.findOne({ where: { id } });

    if (!canal) {
      throw new ApiError(404, 'Canal not found');
    }

    canal.geometry = geometry;
    canal.length = turf.length(turf.feature(geometry), { units: 'meters' });
    canal.updatedAt = new Date();

    const updatedCanal = await this.canalRepository.save(canal);

    // Clear cache
    await cacheService.delete(`canal:${id}`);
    await cacheService.clearPattern('canals:*');
    await cacheService.clearPattern('tile:canals:*');

    return updatedCanal;
  }

  async deleteCanal(id: string): Promise<void> {
    const canal = await this.canalRepository.findOne({
      where: { id },
      relations: ['gates'],
    });

    if (!canal) {
      throw new ApiError(404, 'Canal not found');
    }

    // Check if canal has connected gates
    if (canal.gates && canal.gates.length > 0) {
      throw new ApiError(400, 'Cannot delete canal with connected gates');
    }

    await this.canalRepository.remove(canal);

    // Clear cache
    await cacheService.delete(`canal:${id}`);
    await cacheService.clearPattern('canals:*');
    await cacheService.clearPattern('tile:canals:*');
  }

  async analyzeNetwork(analysisData: any): Promise<any> {
    const { sourceId, targetIds, analysisType } = analysisData;

    // Perform network analysis based on type
    switch (analysisType) {
      case 'connectivity':
        return this.analyzeConnectivity(sourceId, targetIds);
      case 'flow_path':
        return this.analyzeFlowPath(sourceId, targetIds);
      case 'capacity':
        return this.analyzeCapacity(sourceId, targetIds);
      default:
        throw new ApiError(400, 'Invalid analysis type');
    }
  }

  private async analyzeConnectivity(sourceId: string, targetIds: string[]): Promise<any> {
    // Implement connectivity analysis
    return {
      source: sourceId,
      targets: targetIds,
      connected: targetIds.map(id => ({
        targetId: id,
        isConnected: true, // Simplified
        pathLength: 3, // Number of segments
      })),
    };
  }

  private async analyzeFlowPath(sourceId: string, targetIds: string[]): Promise<any> {
    // Implement flow path analysis
    return {
      source: sourceId,
      targets: targetIds,
      flowPaths: targetIds.map(id => ({
        targetId: id,
        path: [sourceId, 'CANAL_002', 'CANAL_003', id],
        totalLength: 5430, // meters
        minCapacity: 3.5, // m³/s
      })),
    };
  }

  private async analyzeCapacity(sourceId: string, targetIds: string[]): Promise<any> {
    // Implement capacity analysis
    return {
      source: sourceId,
      targets: targetIds,
      capacityAnalysis: {
        totalDemand: 12.5, // m³/s
        availableCapacity: 15.0, // m³/s
        utilizationPercentage: 83.3,
        bottlenecks: [],
      },
    };
  }

  async optimizeFlow(optimizationData: any): Promise<any> {
    const { constraints, objectives } = optimizationData;

    // This would implement flow optimization algorithms
    // For now, return mock optimization results
    return {
      status: 'optimal',
      objectives: {
        waterDistribution: 0.95, // 95% efficiency
        energyUsage: 0.85, // 85% efficiency
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

  async identifyBottlenecks(options: any): Promise<any[]> {
    const { threshold, includeRecommendations } = options;

    // Query canals operating above threshold capacity
    // TODO: Implement flow tracking to identify bottlenecks
    // For now, return empty array as currentFlow is not tracked in Canal entity
    const bottlenecks: Canal[] = [];
    
    const results = bottlenecks.map(canal => ({
      canalId: canal.id,
      code: canal.code,
      name: canal.name,
      utilizationPercentage: 0, // Placeholder until flow tracking is implemented
      severity: 'unknown',
      recommendations: includeRecommendations ? this.getBottleneckRecommendations(canal) : undefined,
    }));

    return results;
  }

  private getBottleneckRecommendations(canal: Canal): string[] {
    const recommendations: string[] = [];
    // TODO: Implement when flow tracking is added
    // const utilization = canal.currentFlow / canal.capacity;

    // For now, return generic recommendations
    recommendations.push('Monitor canal conditions');
    recommendations.push('Schedule regular maintenance');

    if (canal.type === CanalType.SUB_LATERAL || canal.type === CanalType.FIELD) {
      recommendations.push('Implement rotation schedule for connected parcels');
    }

    return recommendations;
  }

  async bulkImportCanals(data: any, format: string): Promise<any> {
    let features: Feature[];

    if (format === 'geojson') {
      const featureCollection = data as FeatureCollection;
      features = featureCollection.features;
    } else {
      throw new ApiError(400, 'Unsupported format');
    }

    const canals: Canal[] = [];
    const errors: any[] = [];

    for (const feature of features) {
      try {
        const canal = this.canalRepository.create({
          code: feature.properties?.code || `CANAL_${Date.now()}`,
          name: feature.properties?.name || 'Unnamed Canal',
          type: feature.properties?.type || CanalType.SUB_LATERAL,
          geometry: feature.geometry as LineString,
          length: turf.length(feature, { units: 'meters' }),
          width: feature.properties?.width,
          depth: feature.properties?.depth,
          designCapacity: feature.properties?.capacity || 1.0,
          liningType: feature.properties?.material,
          status: CanalStatus.OPERATIONAL,
          zoneId: feature.properties?.zoneId || 'default-zone', // TODO: Properly map zone
          startPoint: {
            lat: 0, // TODO: Extract from geometry
            lng: 0,
          },
          endPoint: {
            lat: 0, // TODO: Extract from geometry
            lng: 0,
          },
          createdAt: new Date(),
          updatedAt: new Date(),
        });

        canals.push(canal);
      } catch (error: any) {
        errors.push({
          feature: feature.properties?.code || 'unknown',
          error: error.message,
        });
      }
    }

    const savedCanals = await this.canalRepository.save(canals);

    // Clear cache
    await cacheService.clearPattern('canals:*');
    await cacheService.clearPattern('tile:canals:*');

    return {
      imported: savedCanals.length,
      errors: errors.length,
      errorDetails: errors,
    };
  }

  async bulkUpdateCanals(canals: any[]): Promise<any> {
    const updates: Canal[] = [];
    const errors: any[] = [];

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
      } catch (error: any) {
        errors.push({
          id: canalData.id,
          error: error.message,
        });
      }
    }

    const savedCanals = await this.canalRepository.save(updates);

    // Clear cache
    await cacheService.clearPattern('canals:*');
    await cacheService.clearPattern('canal:*');
    await cacheService.clearPattern('tile:canals:*');

    return {
      updated: savedCanals.length,
      errors: errors.length,
      errorDetails: errors,
    };
  }
}

export const canalService = new CanalService();