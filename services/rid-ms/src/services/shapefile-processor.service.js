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
exports.ShapeFileProcessorService = void 0;
const fs = __importStar(require("fs/promises"));
const path = __importStar(require("path"));
const adm_zip_1 = __importDefault(require("adm-zip"));
const shapefile_1 = require("shapefile");
const proj4_1 = __importDefault(require("proj4"));
const turf = __importStar(require("@turf/turf"));
const uuid_1 = require("uuid");
const logger_1 = require("../utils/logger");
const config_1 = require("../config");
const database_service_1 = require("./database.service");
const kafka_service_1 = require("./kafka.service");
class ShapeFileProcessorService {
    static instance;
    databaseService;
    kafkaService;
    constructor() {
        this.databaseService = database_service_1.DatabaseService.getInstance();
        this.kafkaService = kafka_service_1.KafkaService.getInstance();
    }
    static getInstance() {
        if (!ShapeFileProcessorService.instance) {
            ShapeFileProcessorService.instance = new ShapeFileProcessorService();
        }
        return ShapeFileProcessorService.instance;
    }
    async processShapeFile(filePath, metadata) {
        const startTime = Date.now();
        const shapeFileId = (0, uuid_1.v4)();
        const errors = [];
        let parcelsProcessed = 0;
        let parcelsWithErrors = 0;
        try {
            const processingDir = path.join(config_1.config.fileProcessing.processedDir, shapeFileId);
            await fs.mkdir(processingDir, { recursive: true });
            let shapeFilePath;
            if (filePath.endsWith('.zip')) {
                shapeFilePath = await this.extractZipFile(filePath, processingDir);
            }
            else {
                shapeFilePath = filePath;
            }
            const fullMetadata = {
                id: shapeFileId,
                originalFileName: metadata.originalFileName || path.basename(filePath),
                uploadDate: new Date(),
                status: 'processing',
                fileSize: (await fs.stat(filePath)).size,
                coordinateSystem: config_1.config.waterDemand.coordinateSystem,
                ...metadata,
            };
            await this.databaseService.saveShapeFileMetadata(fullMetadata);
            const geoJson = await this.readShapeFile(shapeFilePath);
            const parcels = await this.processParcels(geoJson, shapeFileId);
            for (let i = 0; i < parcels.length; i += config_1.config.fileProcessing.batchSize) {
                const batch = parcels.slice(i, i + config_1.config.fileProcessing.batchSize);
                try {
                    await this.databaseService.saveParcels(batch);
                    parcelsProcessed += batch.length;
                }
                catch (error) {
                    parcelsWithErrors += batch.length;
                    errors.push({
                        errorCode: 'BATCH_SAVE_ERROR',
                        message: `Failed to save batch ${i / config_1.config.fileProcessing.batchSize + 1}`,
                        details: error,
                    });
                }
            }
            fullMetadata.status = 'processed';
            fullMetadata.processedDate = new Date();
            fullMetadata.featureCount = parcels.length;
            fullMetadata.boundingBox = this.calculateBoundingBox(geoJson);
            await this.databaseService.updateShapeFileMetadata(fullMetadata);
            await this.kafkaService.publishShapeFileProcessed({
                shapeFileId,
                parcelsCount: parcels.length,
                processedAt: new Date(),
            });
            await this.archiveFile(filePath, shapeFileId);
            return {
                shapeFileId,
                success: true,
                parcelsProcessed,
                parcelsWithErrors,
                processingTime: Date.now() - startTime,
                errors: errors.length > 0 ? errors : undefined,
            };
        }
        catch (error) {
            logger_1.logger.error('Shape file processing failed:', error);
            await this.databaseService.updateShapeFileMetadata({
                id: shapeFileId,
                status: 'failed',
                error: error instanceof Error ? error.message : 'Unknown error',
            });
            await this.kafkaService.publishProcessingError({
                shapeFileId,
                error: error instanceof Error ? error.message : 'Unknown error',
                timestamp: new Date(),
            });
            return {
                shapeFileId,
                success: false,
                parcelsProcessed,
                parcelsWithErrors,
                processingTime: Date.now() - startTime,
                errors: [
                    {
                        errorCode: 'PROCESSING_FAILED',
                        message: error instanceof Error ? error.message : 'Unknown error',
                        details: error,
                    },
                ],
            };
        }
    }
    async extractZipFile(zipPath, extractDir) {
        const zip = new adm_zip_1.default(zipPath);
        zip.extractAllTo(extractDir, true);
        const files = await fs.readdir(extractDir);
        const shpFile = files.find(f => f.toLowerCase().endsWith('.shp'));
        if (!shpFile) {
            throw new Error('No .shp file found in zip archive');
        }
        return path.join(extractDir, shpFile);
    }
    async readShapeFile(shapeFilePath) {
        const features = [];
        const source = await (0, shapefile_1.open)(shapeFilePath);
        let result = await source.read();
        while (!result.done) {
            if (result.value) {
                features.push(result.value);
            }
            result = await source.read();
        }
        return {
            type: 'FeatureCollection',
            features,
        };
    }
    async processParcels(geoJson, shapeFileId) {
        const parcels = [];
        for (const feature of geoJson.features) {
            try {
                if (feature.geometry.type !== 'Polygon' && feature.geometry.type !== 'MultiPolygon') {
                    continue;
                }
                const transformedGeometry = this.transformCoordinates(feature.geometry);
                const area = turf.area(transformedGeometry);
                const parcel = {
                    id: (0, uuid_1.v4)(),
                    parcelId: feature.properties?.PARCEL_ID ||
                        feature.properties?.parcel_id ||
                        feature.properties?.ID ||
                        (0, uuid_1.v4)(),
                    geometry: transformedGeometry,
                    area,
                    zone: feature.properties?.ZONE || feature.properties?.zone,
                    subZone: feature.properties?.SUBZONE || feature.properties?.subzone,
                    landUseType: feature.properties?.LAND_USE || feature.properties?.land_use,
                    cropType: feature.properties?.CROP_TYPE || feature.properties?.crop_type,
                    owner: feature.properties?.OWNER || feature.properties?.owner,
                    waterDemandMethod: this.determineWaterDemandMethod(feature.properties),
                    attributes: feature.properties || {},
                };
                if (feature.properties?.PLANTING_DATE) {
                    parcel.plantingDate = new Date(feature.properties.PLANTING_DATE);
                }
                if (feature.properties?.HARVEST_DATE) {
                    parcel.harvestDate = new Date(feature.properties.HARVEST_DATE);
                }
                parcels.push(parcel);
            }
            catch (error) {
                logger_1.logger.error(`Error processing parcel: ${error}`);
            }
        }
        return parcels;
    }
    transformCoordinates(geometry) {
        const sourceProj = config_1.config.waterDemand.coordinateSystem;
        const targetProj = 'EPSG:4326';
        if (sourceProj === targetProj) {
            return geometry;
        }
        const transform = (0, proj4_1.default)(sourceProj, targetProj);
        if (geometry.type === 'Polygon') {
            return {
                type: 'Polygon',
                coordinates: geometry.coordinates.map(ring => ring.map(coord => transform.forward(coord))),
            };
        }
        else {
            return {
                type: 'MultiPolygon',
                coordinates: geometry.coordinates.map(polygon => polygon.map(ring => ring.map(coord => transform.forward(coord)))),
            };
        }
    }
    determineWaterDemandMethod(properties) {
        if (properties?.WATER_DEMAND_METHOD) {
            const method = properties.WATER_DEMAND_METHOD.toUpperCase();
            if (['RID-MS', 'ROS', 'AWD'].includes(method)) {
                return method;
            }
        }
        return config_1.config.waterDemand.defaultMethod;
    }
    calculateBoundingBox(geoJson) {
        const bbox = turf.bbox(geoJson);
        return {
            minX: bbox[0],
            minY: bbox[1],
            maxX: bbox[2],
            maxY: bbox[3],
        };
    }
    async archiveFile(filePath, shapeFileId) {
        const archivePath = path.join(config_1.config.fileProcessing.archiveDir, `${shapeFileId}_${path.basename(filePath)}`);
        await fs.mkdir(path.dirname(archivePath), { recursive: true });
        await fs.rename(filePath, archivePath);
    }
    async cleanupOldFiles() {
        const cutoffDate = new Date();
        cutoffDate.setDate(cutoffDate.getDate() - config_1.config.fileProcessing.retentionDays);
        const archiveFiles = await fs.readdir(config_1.config.fileProcessing.archiveDir);
        for (const file of archiveFiles) {
            const filePath = path.join(config_1.config.fileProcessing.archiveDir, file);
            const stats = await fs.stat(filePath);
            if (stats.mtime < cutoffDate) {
                await fs.unlink(filePath);
                logger_1.logger.info(`Deleted old archive file: ${file}`);
            }
        }
        const processedDirs = await fs.readdir(config_1.config.fileProcessing.processedDir);
        for (const dir of processedDirs) {
            const dirPath = path.join(config_1.config.fileProcessing.processedDir, dir);
            const stats = await fs.stat(dirPath);
            if (stats.mtime < cutoffDate) {
                await fs.rm(dirPath, { recursive: true, force: true });
                logger_1.logger.info(`Deleted old processed directory: ${dir}`);
            }
        }
    }
}
exports.ShapeFileProcessorService = ShapeFileProcessorService;
//# sourceMappingURL=shapefile-processor.service.js.map