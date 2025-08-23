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
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.tileService = void 0;
const vtpbf = __importStar(require("vt-pbf"));
const geojson_vt_1 = __importDefault(require("geojson-vt"));
const database_1 = require("../config/database");
const config_1 = require("../config");
const cache_service_1 = require("./cache.service");
const logger_1 = require("../utils/logger");
class TileService {
    tileCache = new Map();
    tileIndices = new Map();
    async getTile(request) {
        const { z, x, y, layer } = request;
        const cacheKey = `tile:${layer}:${z}:${x}:${y}`;
        if (config_1.config.tiles.cacheEnabled) {
            const cached = await cache_service_1.cacheService.get(cacheKey);
            if (cached) {
                return Buffer.from(cached, 'base64');
            }
        }
        try {
            const features = await this.getFeaturesForTile(layer, z, x, y);
            if (features.features.length === 0) {
                return Buffer.alloc(0);
            }
            const tile = await this.generateVectorTile(layer, features, z, x, y);
            if (config_1.config.tiles.cacheEnabled && tile.length > 0) {
                await cache_service_1.cacheService.set(cacheKey, tile.toString('base64'), 3600);
            }
            return tile;
        }
        catch (error) {
            logger_1.logger.error('Error generating tile:', error);
            throw error;
        }
    }
    async getFeaturesForTile(layer, z, x, y) {
        const bounds = this.tileToBounds(z, x, y);
        let query;
        let tableName;
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
        const results = await database_1.AppDataSource.query(query);
        const features = results.map((row) => ({
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
    buildTileQuery(tableName, bounds, zoom, options = {}) {
        const { simplify = true, properties = ['*'] } = options;
        const tolerance = simplify ? this.getSimplificationTolerance(zoom) : 0;
        return `
      WITH bounds AS (
        SELECT ST_MakeEnvelope(${bounds.join(',')}, 4326) AS geom
      )
      SELECT 
        id,
        ${properties.filter((p) => p !== '*' && p !== 'id').map((p) => `"${p}"`).join(', ')},
        ST_AsGeoJSON(
          ${simplify ? `ST_Simplify(geometry, ${tolerance})` : 'geometry'}
        ) as geojson
      FROM ${config_1.config.database.gisSchema}.${tableName}, bounds
      WHERE ST_Intersects(geometry, bounds.geom)
      ${zoom < 10 ? `AND area_hectares > ${this.getAreaThreshold(zoom) / 10000}` : ''}
    `;
    }
    buildPointQuery(tableName, bounds, zoom) {
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
      FROM ${config_1.config.database.gisSchema}.${tableName}, bounds
      WHERE ST_Contains(bounds.geom, location)
    `;
    }
    async generateVectorTile(layer, features, z, x, y) {
        let tileIndex = this.tileIndices.get(layer);
        if (!tileIndex || this.shouldRegenerateTileIndex(layer)) {
            tileIndex = (0, geojson_vt_1.default)(features, {
                maxZoom: config_1.config.tiles.maxZoom,
                tolerance: 3,
                extent: 4096,
                buffer: 64,
                promoteId: 'id',
            });
            this.tileIndices.set(layer, tileIndex);
        }
        const tile = tileIndex.getTile(z, x, y);
        if (!tile) {
            return Buffer.alloc(0);
        }
        const pbf = vtpbf.fromGeojsonVt({ [layer]: tile }, { version: 2 });
        return Buffer.from(pbf);
    }
    tileToBounds(z, x, y) {
        const n = Math.pow(2, z);
        const minLng = (x / n) * 360 - 180;
        const maxLng = ((x + 1) / n) * 360 - 180;
        const minLat = Math.atan(Math.sinh(Math.PI * (1 - 2 * (y + 1) / n))) * 180 / Math.PI;
        const maxLat = Math.atan(Math.sinh(Math.PI * (1 - 2 * y / n))) * 180 / Math.PI;
        return [minLng, minLat, maxLng, maxLat];
    }
    getSimplificationTolerance(zoom) {
        if (zoom < 8)
            return 0.01;
        if (zoom < 10)
            return 0.001;
        if (zoom < 12)
            return 0.0001;
        if (zoom < 14)
            return 0.00001;
        return 0;
    }
    getAreaThreshold(zoom) {
        if (zoom < 8)
            return 1000000;
        if (zoom < 10)
            return 100000;
        if (zoom < 12)
            return 10000;
        return 0;
    }
    shouldRegenerateTileIndex(layer) {
        return false;
    }
    extractProperties(row, excludeKeys = []) {
        const properties = {};
        Object.keys(row).forEach(key => {
            if (!excludeKeys.includes(key)) {
                properties[key] = row[key];
            }
        });
        return properties;
    }
    async clearTileCache(layer) {
        if (layer) {
            this.tileIndices.delete(layer);
            await cache_service_1.cacheService.clearPattern(`tile:${layer}:*`);
        }
        else {
            this.tileIndices.clear();
            await cache_service_1.cacheService.clearPattern('tile:*');
        }
    }
    async preGenerateTiles(layer, minZoom, maxZoom, bounds) {
        logger_1.logger.info(`Pre-generating tiles for ${layer} from zoom ${minZoom} to ${maxZoom}`);
    }
}
exports.tileService = new TileService();
//# sourceMappingURL=tile.service.js.map