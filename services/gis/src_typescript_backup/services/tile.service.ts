import * as vtpbf from 'vt-pbf';
import geojsonvt from 'geojson-vt';
import { Repository } from 'typeorm';
import { AppDataSource } from '../config/database';
import { config } from '../config';
import { cacheService } from './cache.service';
import { logger } from '../utils/logger';
import { Feature, FeatureCollection } from 'geojson';

interface TileRequest {
  z: number;
  x: number;
  y: number;
  layer: string;
}

interface TileOptions {
  maxZoom?: number;
  tolerance?: number;
  extent?: number;
  buffer?: number;
  promoteId?: string | null;
}

class TileService {
  private tileCache = new Map<string, any>();
  private tileIndices = new Map<string, any>();

  async getTile(request: TileRequest): Promise<Buffer> {
    const { z, x, y, layer } = request;
    const cacheKey = `tile:${layer}:${z}:${x}:${y}`;

    // Check cache
    if (config.tiles.cacheEnabled) {
      const cached = await cacheService.get(cacheKey);
      if (cached) {
        return Buffer.from(cached, 'base64');
      }
    }

    try {
      // Get features for tile
      const features = await this.getFeaturesForTile(layer, z, x, y);
      
      if (features.features.length === 0) {
        // Return empty tile
        return Buffer.alloc(0);
      }

      // Generate vector tile
      const tile = await this.generateVectorTile(layer, features, z, x, y);

      // Cache tile
      if (config.tiles.cacheEnabled && tile.length > 0) {
        await cacheService.set(cacheKey, tile.toString('base64'), 3600); // 1 hour
      }

      return tile;
    } catch (error) {
      logger.error('Error generating tile:', error);
      throw error;
    }
  }

  private async getFeaturesForTile(
    layer: string,
    z: number,
    x: number,
    y: number
  ): Promise<FeatureCollection> {
    // Calculate tile bounds
    const bounds = this.tileToBounds(z, x, y);
    
    // Build query based on layer
    let query: string;
    let tableName: string;

    switch (layer) {
      case 'zones':
        tableName = 'irrigation_zones';
        query = this.buildTileQuery(tableName, bounds, z);
        break;
      case 'parcels':
        tableName = 'agricultural_plots';
        query = this.buildTileQuery(tableName, bounds, z, {
          simplify: z < 15,
          properties: ['id', 'plot_code', 'area_hectares', 'current_crop_type', 'farmer_id'],
        });
        break;
      case 'canals':
        tableName = 'canal_network';
        query = this.buildTileQuery(tableName, bounds, z, {
          simplify: z < 14,
          properties: ['id', 'canal_code', 'canal_name', 'canal_type', 'capacity_cms'],
        });
        break;
      case 'gates':
        tableName = 'control_structures';
        query = this.buildPointQuery(tableName, bounds, z);
        break;
      case 'pumps':
        tableName = 'control_structures';
        query = this.buildPointQuery(tableName, bounds, z);
        break;
      default:
        throw new Error(`Unknown layer: ${layer}`);
    }

    const results = await AppDataSource.query(query);
    
    const features = results.map((row: any) => ({
      type: 'Feature',
      id: row.id,
      geometry: JSON.parse(row.geojson),
      properties: this.extractProperties(row, ['id', 'geojson']),
    }));

    return {
      type: 'FeatureCollection',
      features,
    };
  }

  private buildTileQuery(
    tableName: string,
    bounds: number[],
    zoom: number,
    options: any = {}
  ): string {
    const { simplify = true, properties = ['*'] } = options;
    const tolerance = simplify ? this.getSimplificationTolerance(zoom) : 0;

    return `
      WITH bounds AS (
        SELECT ST_MakeEnvelope(${bounds.join(',')}, 4326) AS geom
      )
      SELECT 
        id,
        ${properties.filter((p: string) => p !== '*' && p !== 'id').map((p: string) => `"${p}"`).join(', ')},
        ST_AsGeoJSON(
          ${simplify ? `ST_Simplify(geometry, ${tolerance})` : 'geometry'}
        ) as geojson
      FROM ${config.database.gisSchema}.${tableName}, bounds
      WHERE ST_Intersects(geometry, bounds.geom)
      ${zoom < 10 ? `AND area_hectares > ${this.getAreaThreshold(zoom) / 10000}` : ''}
    `;
  }

  private buildPointQuery(
    tableName: string,
    bounds: number[],
    zoom: number
  ): string {
    return `
      WITH bounds AS (
        SELECT ST_MakeEnvelope(${bounds.join(',')}, 4326) AS geom
      )
      SELECT 
        id,
        structure_code,
        structure_name,
        structure_type,
        operational_status,
        ST_AsGeoJSON(location) as geojson
      FROM ${config.database.gisSchema}.${tableName}, bounds
      WHERE ST_Contains(bounds.geom, location)
    `;
  }

  private async generateVectorTile(
    layer: string,
    features: FeatureCollection,
    z: number,
    x: number,
    y: number
  ): Promise<Buffer> {
    // Get or create tile index
    let tileIndex = this.tileIndices.get(layer);
    
    if (!tileIndex || this.shouldRegenerateTileIndex(layer)) {
      tileIndex = geojsonvt(features, {
        maxZoom: config.tiles.maxZoom,
        tolerance: 3,
        extent: 4096,
        buffer: 64,
        promoteId: 'id',
      });
      this.tileIndices.set(layer, tileIndex);
    }

    // Get tile data
    const tile = tileIndex.getTile(z, x, y);
    
    if (!tile) {
      return Buffer.alloc(0);
    }

    // Convert to vector tile format
    const pbf = vtpbf.fromGeojsonVt({ [layer]: tile }, { version: 2 });
    return Buffer.from(pbf);
  }

  private tileToBounds(z: number, x: number, y: number): number[] {
    const n = Math.pow(2, z);
    const minLng = (x / n) * 360 - 180;
    const maxLng = ((x + 1) / n) * 360 - 180;
    const minLat = Math.atan(Math.sinh(Math.PI * (1 - 2 * (y + 1) / n))) * 180 / Math.PI;
    const maxLat = Math.atan(Math.sinh(Math.PI * (1 - 2 * y / n))) * 180 / Math.PI;
    return [minLng, minLat, maxLng, maxLat];
  }

  private getSimplificationTolerance(zoom: number): number {
    // More aggressive simplification at lower zoom levels
    if (zoom < 8) return 0.01;
    if (zoom < 10) return 0.001;
    if (zoom < 12) return 0.0001;
    if (zoom < 14) return 0.00001;
    return 0;
  }

  private getAreaThreshold(zoom: number): number {
    // Filter out small features at lower zoom levels
    if (zoom < 8) return 1000000; // 1 km²
    if (zoom < 10) return 100000; // 0.1 km²
    if (zoom < 12) return 10000; // 0.01 km²
    return 0;
  }

  private shouldRegenerateTileIndex(layer: string): boolean {
    // Logic to determine if tile index should be regenerated
    // For now, always use cached index
    return false;
  }

  private extractProperties(row: any, excludeKeys: string[] = []): any {
    const properties: any = {};
    
    Object.keys(row).forEach(key => {
      if (!excludeKeys.includes(key)) {
        properties[key] = row[key];
      }
    });
    
    return properties;
  }

  async clearTileCache(layer?: string): Promise<void> {
    if (layer) {
      this.tileIndices.delete(layer);
      // Clear Redis cache for specific layer
      await cacheService.clearPattern(`tile:${layer}:*`);
    } else {
      this.tileIndices.clear();
      // Clear all tile cache
      await cacheService.clearPattern('tile:*');
    }
  }

  async preGenerateTiles(layer: string, minZoom: number, maxZoom: number, bounds?: number[]): Promise<void> {
    // Pre-generate tiles for better performance
    // This would be called during off-peak hours
    logger.info(`Pre-generating tiles for ${layer} from zoom ${minZoom} to ${maxZoom}`);
    
    // Implementation would generate tiles for the specified zoom range
    // and store them in cache
  }
}

export const tileService = new TileService();