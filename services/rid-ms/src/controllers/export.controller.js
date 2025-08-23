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
exports.ExportController = void 0;
const pg_1 = require("pg");
const logger_1 = require("../utils/logger");
const turf = __importStar(require("@turf/turf"));
class ExportController {
    db;
    constructor() {
        this.db = new pg_1.Pool({
            connectionString: process.env.DATABASE_URL || 'postgresql://postgres:postgres123@localhost:5435/rid_ms',
        });
    }
    async exportParcelsGeoJSON(req, res) {
        const { zone, cropType, waterDemandMethod, includeWaterDemand, limit = 10000, simplify = false, precision = 6, } = req.query;
        try {
            let query = `
        SELECT 
          p.id,
          p.parcel_id,
          p.zone,
          p.sub_zone,
          p.area_rai,
          p.area_sqm,
          p.crop_type,
          p.owner_name,
          p.owner_id,
          p.water_demand_method,
          p.planting_date,
          p.harvest_date,
          ST_AsGeoJSON(p.geometry, ${precision}) as geometry
          ${includeWaterDemand ? ', wdc.daily_demand_cubic_meters, wdc.method as calc_method' : ''}
        FROM parcels p
        ${includeWaterDemand ? 'LEFT JOIN water_demand_calculations wdc ON p.id = wdc.parcel_id' : ''}
        WHERE p.valid_to IS NULL
      `;
            const params = [];
            let paramCount = 0;
            if (zone) {
                paramCount++;
                query += ` AND p.zone = $${paramCount}`;
                params.push(zone);
            }
            if (cropType) {
                paramCount++;
                query += ` AND p.crop_type = $${paramCount}`;
                params.push(cropType);
            }
            if (waterDemandMethod) {
                paramCount++;
                query += ` AND p.water_demand_method = $${paramCount}`;
                params.push(waterDemandMethod);
            }
            paramCount++;
            query += ` LIMIT $${paramCount}`;
            params.push(limit);
            const result = await this.db.query(query, params);
            const features = result.rows.map(row => {
                const geometry = JSON.parse(row.geometry);
                const finalGeometry = simplify === 'true'
                    ? turf.simplify(geometry, { tolerance: 0.00001, highQuality: false })
                    : geometry;
                const properties = {
                    id: row.id,
                    parcelId: row.parcel_id,
                    zone: row.zone,
                    subZone: row.sub_zone,
                    areaRai: parseFloat(row.area_rai),
                    areaSqm: parseFloat(row.area_sqm),
                    cropType: row.crop_type,
                    ownerName: row.owner_name,
                    ownerId: row.owner_id,
                    waterDemandMethod: row.water_demand_method,
                    plantingDate: row.planting_date,
                    harvestDate: row.harvest_date,
                };
                if (includeWaterDemand && row.daily_demand_cubic_meters) {
                    properties.waterDemand = {
                        dailyCubicMeters: parseFloat(row.daily_demand_cubic_meters),
                        method: row.calc_method,
                    };
                }
                return {
                    type: 'Feature',
                    properties,
                    geometry: finalGeometry,
                };
            });
            const geojson = {
                type: 'FeatureCollection',
                features,
                metadata: {
                    totalFeatures: features.length,
                    filters: { zone, cropType, waterDemandMethod },
                    precision,
                    simplified: simplify === 'true',
                    includesWaterDemand: includeWaterDemand === 'true',
                    exportedAt: new Date().toISOString(),
                },
            };
            res.json(geojson);
        }
        catch (error) {
            logger_1.logger.error('Error exporting parcels GeoJSON:', error);
            res.status(500).json({ error: 'Failed to export parcels as GeoJSON' });
        }
    }
    async exportZonesGeoJSON(req, res) {
        const { includeStats, includeWaterDemand } = req.query;
        try {
            const query = `
        SELECT 
          zone,
          ST_AsGeoJSON(ST_Union(geometry)) as geometry,
          COUNT(*) as parcel_count,
          SUM(area_rai) as total_area_rai,
          SUM(area_sqm) as total_area_sqm
        FROM parcels
        WHERE valid_to IS NULL
        GROUP BY zone
        ORDER BY zone
      `;
            const result = await this.db.query(query);
            const featuresPromises = result.rows.map(async (row) => {
                const properties = {
                    zone: row.zone,
                    parcelCount: parseInt(row.parcel_count),
                    totalAreaRai: parseFloat(row.total_area_rai),
                    totalAreaSqm: parseFloat(row.total_area_sqm),
                };
                if (includeStats === 'true') {
                    const cropQuery = `
            SELECT 
              crop_type,
              COUNT(*) as count,
              SUM(area_rai) as area_rai
            FROM parcels
            WHERE zone = $1 AND valid_to IS NULL AND crop_type IS NOT NULL
            GROUP BY crop_type
          `;
                    const cropResult = await this.db.query(cropQuery, [row.zone]);
                    properties.cropDistribution = cropResult.rows;
                }
                if (includeWaterDemand === 'true') {
                    const waterDemandQuery = `
            SELECT 
              SUM(wdc.daily_demand_cubic_meters) as total_daily_demand,
              AVG(wdc.daily_demand_cubic_meters) as avg_daily_demand
            FROM parcels p
            JOIN water_demand_calculations wdc ON p.id = wdc.parcel_id
            WHERE p.zone = $1 AND p.valid_to IS NULL
          `;
                    const waterDemandResult = await this.db.query(waterDemandQuery, [row.zone]);
                    if (waterDemandResult.rows[0].total_daily_demand) {
                        properties.waterDemand = {
                            totalDailyCubicMeters: parseFloat(waterDemandResult.rows[0].total_daily_demand),
                            avgDailyCubicMeters: parseFloat(waterDemandResult.rows[0].avg_daily_demand),
                        };
                    }
                }
                return {
                    type: 'Feature',
                    properties,
                    geometry: JSON.parse(row.geometry),
                };
            });
            const features = await Promise.all(featuresPromises);
            const geojson = {
                type: 'FeatureCollection',
                features,
                metadata: {
                    totalZones: features.length,
                    includesStats: includeStats === 'true',
                    includesWaterDemand: includeWaterDemand === 'true',
                    exportedAt: new Date().toISOString(),
                },
            };
            res.json(geojson);
        }
        catch (error) {
            logger_1.logger.error('Error exporting zones GeoJSON:', error);
            res.status(500).json({ error: 'Failed to export zones as GeoJSON' });
        }
    }
    async exportWaterDemandHeatmap(req, res) {
        const { zone, method, date, resolution = 'medium' } = req.query;
        try {
            const gridSizes = {
                high: 0.001,
                medium: 0.005,
                low: 0.01,
            };
            const gridSize = gridSizes[resolution] || gridSizes.medium;
            let query = `
        WITH grid AS (
          SELECT 
            ST_SquareGrid(${gridSize}, ST_Envelope(ST_Union(p.geometry))) AS cell
          FROM parcels p
          WHERE p.valid_to IS NULL
          ${zone ? 'AND p.zone = $1' : ''}
        )
        SELECT 
          ST_AsGeoJSON(grid.cell) as geometry,
          COUNT(p.id) as parcel_count,
          SUM(wdc.daily_demand_cubic_meters) as total_demand,
          AVG(wdc.daily_demand_cubic_meters) as avg_demand,
          SUM(p.area_rai) as total_area_rai
        FROM grid
        JOIN parcels p ON ST_Intersects(p.geometry, grid.cell)
        LEFT JOIN water_demand_calculations wdc ON p.id = wdc.parcel_id
        WHERE p.valid_to IS NULL
        ${zone ? 'AND p.zone = $1' : ''}
        ${method ? `AND p.water_demand_method = $${zone ? 2 : 1}` : ''}
        GROUP BY grid.cell
        HAVING COUNT(p.id) > 0
      `;
            const params = [];
            if (zone)
                params.push(zone);
            if (method && !zone)
                params.push(method);
            if (method && zone)
                params.push(method);
            const alternativeQuery = `
        WITH bounds AS (
          SELECT 
            ST_XMin(ST_Extent(geometry)) as xmin,
            ST_YMin(ST_Extent(geometry)) as ymin,
            ST_XMax(ST_Extent(geometry)) as xmax,
            ST_YMax(ST_Extent(geometry)) as ymax
          FROM parcels
          WHERE valid_to IS NULL
          ${zone ? 'AND zone = $1' : ''}
        ),
        grid_points AS (
          SELECT 
            ST_MakePoint(x, y) as point,
            ST_MakeEnvelope(x, y, x + ${gridSize}, y + ${gridSize}, 4326) as cell
          FROM bounds,
          generate_series(
            floor(xmin/${gridSize})*${gridSize}, 
            ceil(xmax/${gridSize})*${gridSize}, 
            ${gridSize}
          ) as x,
          generate_series(
            floor(ymin/${gridSize})*${gridSize}, 
            ceil(ymax/${gridSize})*${gridSize}, 
            ${gridSize}
          ) as y
        )
        SELECT 
          ST_AsGeoJSON(gp.cell) as geometry,
          COUNT(p.id) as parcel_count,
          COALESCE(SUM(wdc.daily_demand_cubic_meters), 0) as total_demand,
          COALESCE(AVG(wdc.daily_demand_cubic_meters), 0) as avg_demand,
          COALESCE(SUM(p.area_rai), 0) as total_area_rai
        FROM grid_points gp
        LEFT JOIN parcels p ON ST_Intersects(p.geometry, gp.cell) AND p.valid_to IS NULL
        LEFT JOIN water_demand_calculations wdc ON p.id = wdc.parcel_id
        WHERE 1=1
        ${zone ? 'AND p.zone = $1' : ''}
        ${method ? `AND p.water_demand_method = $${zone ? 2 : 1}` : ''}
        GROUP BY gp.cell
        HAVING COUNT(p.id) > 0
      `;
            const result = await this.db.query(alternativeQuery, params);
            const features = result.rows.map(row => ({
                type: 'Feature',
                properties: {
                    parcelCount: parseInt(row.parcel_count),
                    totalDemandCubicMeters: parseFloat(row.total_demand || 0),
                    avgDemandCubicMeters: parseFloat(row.avg_demand || 0),
                    totalAreaRai: parseFloat(row.total_area_rai || 0),
                    demandIntensity: row.total_area_rai > 0
                        ? parseFloat(row.total_demand || 0) / parseFloat(row.total_area_rai)
                        : 0,
                },
                geometry: JSON.parse(row.geometry),
            }));
            const intensities = features.map(f => f.properties.demandIntensity);
            const maxIntensity = Math.max(...intensities);
            const minIntensity = Math.min(...intensities);
            features.forEach(feature => {
                const normalized = (feature.properties.demandIntensity - minIntensity) /
                    (maxIntensity - minIntensity);
                feature.properties.color = this.getHeatmapColor(normalized);
            });
            const geojson = {
                type: 'FeatureCollection',
                features,
                metadata: {
                    resolution,
                    gridSize,
                    totalCells: features.length,
                    filters: { zone, method, date },
                    intensityRange: { min: minIntensity, max: maxIntensity },
                    exportedAt: new Date().toISOString(),
                },
            };
            res.json(geojson);
        }
        catch (error) {
            logger_1.logger.error('Error exporting water demand heatmap:', error);
            res.status(500).json({ error: 'Failed to export water demand heatmap' });
        }
    }
    async customExport(req, res) {
        const { type, filters = {}, attributes = [], format = 'geojson', simplify, precision = 6 } = req.body;
        try {
            if (format !== 'geojson') {
                return res.status(400).json({ error: 'Only GeoJSON format is currently supported' });
            }
            let baseQuery = '';
            const params = [];
            let paramCount = 0;
            switch (type) {
                case 'parcels':
                    const selectedAttrs = attributes.length > 0
                        ? attributes.filter(attr => this.isValidAttribute(attr)).join(', ')
                        : 'id, parcel_id, zone, area_rai, crop_type, owner_name';
                    baseQuery = `
            SELECT 
              ${selectedAttrs},
              ST_AsGeoJSON(geometry, ${precision}) as geometry
            FROM parcels
            WHERE valid_to IS NULL
          `;
                    break;
                case 'zones':
                    baseQuery = `
            SELECT 
              zone,
              COUNT(*) as parcel_count,
              SUM(area_rai) as total_area_rai,
              ST_AsGeoJSON(ST_Union(geometry)) as geometry
            FROM parcels
            WHERE valid_to IS NULL
            GROUP BY zone
          `;
                    break;
                default:
                    return res.status(400).json({ error: 'Invalid export type' });
            }
            if (filters && Object.keys(filters).length > 0) {
                Object.entries(filters).forEach(([key, value]) => {
                    if (this.isValidAttribute(key) && value !== undefined) {
                        paramCount++;
                        baseQuery += ` AND ${key} = $${paramCount}`;
                        params.push(value);
                    }
                });
            }
            const result = await this.db.query(baseQuery, params);
            const features = result.rows.map(row => {
                const geometry = JSON.parse(row.geometry);
                const { geometry: _, ...properties } = row;
                return {
                    type: 'Feature',
                    properties,
                    geometry: simplify ? turf.simplify(geometry, { tolerance: 0.00001 }) : geometry,
                };
            });
            const geojson = {
                type: 'FeatureCollection',
                features,
                metadata: {
                    exportType: type,
                    totalFeatures: features.length,
                    filters,
                    attributes: attributes.length > 0 ? attributes : 'default',
                    simplified: !!simplify,
                    precision,
                    exportedAt: new Date().toISOString(),
                },
            };
            res.json(geojson);
        }
        catch (error) {
            logger_1.logger.error('Error in custom export:', error);
            res.status(500).json({ error: 'Failed to perform custom export' });
        }
    }
    getHeatmapColor(value) {
        const colors = [
            { value: 0, color: '#0000FF' },
            { value: 0.25, color: '#00FFFF' },
            { value: 0.5, color: '#00FF00' },
            { value: 0.75, color: '#FFFF00' },
            { value: 1, color: '#FF0000' },
        ];
        for (let i = 0; i < colors.length - 1; i++) {
            if (value >= colors[i].value && value <= colors[i + 1].value) {
                const ratio = (value - colors[i].value) / (colors[i + 1].value - colors[i].value);
                return this.interpolateColor(colors[i].color, colors[i + 1].color, ratio);
            }
        }
        return colors[colors.length - 1].color;
    }
    interpolateColor(color1, color2, ratio) {
        const hex = (x) => x.toString(16).padStart(2, '0');
        const r1 = parseInt(color1.slice(1, 3), 16);
        const g1 = parseInt(color1.slice(3, 5), 16);
        const b1 = parseInt(color1.slice(5, 7), 16);
        const r2 = parseInt(color2.slice(1, 3), 16);
        const g2 = parseInt(color2.slice(3, 5), 16);
        const b2 = parseInt(color2.slice(5, 7), 16);
        const r = Math.round(r1 + (r2 - r1) * ratio);
        const g = Math.round(g1 + (g2 - g1) * ratio);
        const b = Math.round(b1 + (b2 - b1) * ratio);
        return `#${hex(r)}${hex(g)}${hex(b)}`;
    }
    isValidAttribute(attr) {
        const validAttributes = [
            'id', 'parcel_id', 'zone', 'sub_zone', 'area_rai', 'area_sqm',
            'crop_type', 'owner_name', 'owner_id', 'water_demand_method',
            'planting_date', 'harvest_date', 'valid_from', 'valid_to',
        ];
        return validAttributes.includes(attr);
    }
}
exports.ExportController = ExportController;
//# sourceMappingURL=export.controller.js.map