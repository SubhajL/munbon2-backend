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
exports.ShapeFileProcessor = void 0;
const adm_zip_1 = __importDefault(require("adm-zip"));
const shapefile_1 = require("shapefile");
const proj4_1 = __importDefault(require("proj4"));
const turf = __importStar(require("@turf/turf"));
const fs = __importStar(require("fs"));
const path = __importStar(require("path"));
const logger_1 = require("../utils/logger");
class ShapeFileProcessor {
    tempDir = '/tmp/gis-shape-files';
    constructor() {
        if (!fs.existsSync(this.tempDir)) {
            fs.mkdirSync(this.tempDir, { recursive: true });
        }
    }
    async processShapeFile(options) {
        const uploadDir = path.join(this.tempDir, options.uploadId);
        try {
            fs.mkdirSync(uploadDir, { recursive: true });
            const zipPath = path.join(uploadDir, options.fileName);
            fs.writeFileSync(zipPath, options.buffer);
            const zip = new adm_zip_1.default(zipPath);
            zip.extractAllTo(uploadDir, true);
            logger_1.logger.info('Extracted shape file archive', { uploadDir });
            const parcels = await this.parseShapeFiles(uploadDir);
            return parcels;
        }
        finally {
            this.cleanupDirectory(uploadDir);
        }
    }
    async parseShapeFiles(directory) {
        const files = fs.readdirSync(directory);
        const shpFile = files.find(f => f.toLowerCase().endsWith('.shp'));
        const gpkgFile = files.find(f => f.toLowerCase().endsWith('.gpkg'));
        const dbfFile = files.find(f => f.toLowerCase().endsWith('.dbf'));
        if (gpkgFile) {
            const gpkgPath = path.join(directory, gpkgFile);
            logger_1.logger.info('Found GeoPackage file in archive', { file: gpkgFile });
            const { GeoPackageProcessor } = await Promise.resolve().then(() => __importStar(require('./geopackage-processor')));
            const geopackageProcessor = new GeoPackageProcessor();
            const results = await geopackageProcessor.processGeoPackageFile(gpkgPath, 'temp-upload');
            const parcels = [];
            for (const result of results) {
                if (result.parcels) {
                    for (const parcel of result.parcels) {
                        const ridAttributes = parcel.properties?.ridAttributes;
                        const formattedRidAttributes = ridAttributes ? {
                            ...ridAttributes,
                            dataDateProcess: ridAttributes.dataDateProcess instanceof Date
                                ? ridAttributes.dataDateProcess.toISOString()
                                : ridAttributes.dataDateProcess,
                            startInt: ridAttributes.startInt instanceof Date
                                ? ridAttributes.startInt.toISOString()
                                : ridAttributes.startInt,
                        } : undefined;
                        parcels.push({
                            parcelId: parcel.plotCode || `P${Date.now()}-${parcels.length}`,
                            geometry: parcel.boundary || parcel.properties?.geometry,
                            area: parcel.areaHectares ? parcel.areaHectares * 10000 : 0,
                            zoneId: String(parcel.zoneId || '1'),
                            attributes: parcel.properties || {},
                            ridAttributes: formattedRidAttributes,
                            cropType: parcel.currentCropType || parcel.properties?.cropType,
                            ownerName: parcel.properties?.ownerName,
                            ownerId: parcel.properties?.ownerId,
                            subZone: parcel.properties?.subZone,
                            landUseType: parcel.properties?.landUseType,
                        });
                    }
                }
            }
            logger_1.logger.info('Parsed parcels from GeoPackage', { count: parcels.length });
            return parcels;
        }
        if (!shpFile) {
            throw new Error('No .shp or .gpkg file found in archive');
        }
        const shpPath = path.join(directory, shpFile);
        const dbfPath = dbfFile ? path.join(directory, dbfFile) : undefined;
        const utm48n = '+proj=utm +zone=48 +datum=WGS84 +units=m +no_defs';
        const wgs84 = '+proj=longlat +datum=WGS84 +no_defs';
        const transform = (0, proj4_1.default)(utm48n, wgs84);
        const parcels = [];
        const source = await (0, shapefile_1.open)(shpPath, dbfPath);
        let result = await source.read();
        let index = 0;
        while (!result.done && result.value) {
            const feature = result.value;
            if (feature.geometry.type !== 'Polygon' && feature.geometry.type !== 'MultiPolygon') {
                result = await source.read();
                continue;
            }
            const transformedGeometry = this.transformCoordinates(feature.geometry, transform);
            const area = turf.area(transformedGeometry);
            const areaHectares = area / 10000;
            const areaRai = areaHectares * 6.25;
            logger_1.logger.debug('Calculated area for shapefile parcel', {
                index,
                areaM2: area,
                areaHectares,
                areaRai
            });
            const props = feature.properties || {};
            const parcel = this.extractParcelProperties(props, index);
            parcels.push({
                parcelId: parcel.parcelId || `P${Date.now()}-${index}`,
                zoneId: parcel.zoneId || '1',
                geometry: transformedGeometry,
                area,
                attributes: props,
                subZone: parcel.subZone,
                ownerName: parcel.ownerName,
                ownerId: parcel.ownerId,
                cropType: parcel.cropType,
                landUseType: parcel.landUseType,
                ridAttributes: parcel.ridAttributes,
            });
            index++;
            result = await source.read();
        }
        logger_1.logger.info('Parsed parcels from shape file', { count: parcels.length });
        return parcels;
    }
    transformCoordinates(geometry, transform) {
        if (geometry.type === 'Polygon') {
            return {
                type: 'Polygon',
                coordinates: geometry.coordinates.map((ring) => ring.map((coord) => transform.forward(coord))),
            };
        }
        else if (geometry.type === 'MultiPolygon') {
            return {
                type: 'MultiPolygon',
                coordinates: geometry.coordinates.map((polygon) => polygon.map((ring) => ring.map((coord) => transform.forward(coord)))),
            };
        }
        return geometry;
    }
    extractParcelProperties(props, index) {
        const fieldMappings = {
            parcelId: ['PARCEL_SEQ', 'PARCEL_ID', 'parcel_id', 'ID', 'id', 'แปลง', 'รหัสแปลง'],
            zone: ['sub_member', 'ZONE', 'zone', 'Zone_ID', 'zone_id', 'โซน'],
            subZone: ['SUBZONE', 'subzone', 'Sub_Zone', 'sub_zone', 'โซนย่อย'],
            ownerName: ['OWNER', 'owner', 'Owner_Name', 'owner_name', 'ชื่อเจ้าของ', 'ชื่อ'],
            ownerId: ['OWNER_ID', 'owner_id', 'Owner_ID', 'รหัสเจ้าของ'],
            cropType: ['plant_id', 'CROP', 'crop', 'Crop_Type', 'crop_type', 'พืช', 'ชนิดพืช'],
            landUseType: ['LANDUSE', 'landuse', 'Land_Use', 'land_use', 'การใช้ที่ดิน'],
        };
        const extracted = {
            parcelId: `P${Date.now()}-${index}`,
        };
        for (const [key, possibleNames] of Object.entries(fieldMappings)) {
            for (const fieldName of possibleNames) {
                if (props[fieldName] !== undefined && props[fieldName] !== null) {
                    extracted[key] = props[fieldName];
                    break;
                }
            }
        }
        if (props.PARCEL_SEQ) {
            extracted.parcelId = props.PARCEL_SEQ;
        }
        if (props.sub_member) {
            extracted.zone = `Zone${props.sub_member}`;
            extracted.zoneId = String(props.sub_member);
        }
        else if (!extracted.zone) {
            extracted.zone = 'Zone1';
            extracted.zoneId = '1';
        }
        else {
            const zoneMatch = String(extracted.zone).match(/\d+/);
            extracted.zoneId = zoneMatch ? zoneMatch[0] : '1';
        }
        extracted.ridAttributes = {
            parcelAreaRai: props.parcel_are,
            dataDateProcess: props.data_date_,
            startInt: props.start_int,
            wpet: props.wpet,
            age: props.age,
            wprod: props.wprod,
            plantId: props.plant_id,
            yieldAtMcKgpr: props.yield_at_m,
            seasonIrrM3PerRai: props.season_irr,
            autoNote: props.auto_note,
            stageAge: props.stage_age,
            lat: props.lat,
            lon: props.lon,
            subMember: props.sub_member,
        };
        return extracted;
    }
    cleanupDirectory(directory) {
        try {
            if (fs.existsSync(directory)) {
                fs.rmSync(directory, { recursive: true, force: true });
            }
        }
        catch (error) {
            logger_1.logger.warn('Failed to cleanup temporary directory', { error, directory });
        }
    }
}
exports.ShapeFileProcessor = ShapeFileProcessor;
//# sourceMappingURL=shapefile-processor.js.map