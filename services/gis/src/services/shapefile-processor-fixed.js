const fs = require('fs');
const path = require('path');
const AdmZip = require('adm-zip');
const { open } = require('shapefile');
const proj4 = require('proj4');
const turf = require('@turf/turf');
const { logger } = require('../utils/logger');

class ShapeFileProcessor {
    constructor() {
        this.tempDir = '/tmp/gis-shape-files';
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
            
            const zip = new AdmZip(zipPath);
            zip.extractAllTo(uploadDir, true);
            logger.info('Extracted shape file archive', { uploadDir });
            
            const parcels = await this.parseShapeFiles(uploadDir);
            return parcels;
        } finally {
            this.cleanupDirectory(uploadDir);
        }
    }

    async parseShapeFiles(directory) {
        const files = fs.readdirSync(directory);
        
        // Discovery logging
        logger.info('Files extracted from archive:', {
            directory,
            totalFiles: files.length,
            files: files.map(file => {
                const filePath = path.join(directory, file);
                const stats = fs.statSync(filePath);
                return {
                    name: file,
                    extension: path.extname(file).toLowerCase(),
                    size: stats.size,
                    isDirectory: stats.isDirectory()
                };
            })
        });
        
        // Search for .gpkg files in all directories (including subdirectories)
        const gpkgFiles = [];
        const searchForGpkg = (dir) => {
            const items = fs.readdirSync(dir);
            for (const item of items) {
                const fullPath = path.join(dir, item);
                const stats = fs.statSync(fullPath);
                
                if (stats.isDirectory()) {
                    // Recursively search subdirectories
                    searchForGpkg(fullPath);
                } else if (item.toLowerCase().endsWith('.gpkg')) {
                    gpkgFiles.push(fullPath);
                } else if (stats.isFile()) {
                    // Check if files without extensions might be geopackages
                    const dirName = path.basename(path.dirname(fullPath));
                    if (dirName === 'data_ridplan' || dirName === 'data_gistda') {
                        // These are likely geopackage files without extensions
                        // Try to identify by reading file header
                        const buffer = fs.readFileSync(fullPath, { length: 16 });
                        if (buffer.toString('utf8', 0, 10) === 'SQLite for') {
                            logger.info(`Found potential GeoPackage without extension: ${item}`);
                            gpkgFiles.push(fullPath);
                        }
                    }
                }
            }
        };
        
        searchForGpkg(directory);
        
        logger.info('Found GeoPackage files:', {
            count: gpkgFiles.length,
            files: gpkgFiles.map(f => path.relative(directory, f))
        });
        
        // Process all found geopackage files
        if (gpkgFiles.length > 0) {
            const allParcels = [];
            const { GeoPackageProcessor } = await import('./geopackage-processor');
            const geopackageProcessor = new GeoPackageProcessor();
            
            for (const gpkgPath of gpkgFiles) {
                try {
                    logger.info('Processing GeoPackage file', { 
                        file: path.relative(directory, gpkgPath),
                        directory: path.basename(path.dirname(gpkgPath))
                    });
                    
                    const results = await geopackageProcessor.processGeoPackageFile(gpkgPath, 'temp-upload');
                    
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
                                
                                allParcels.push({
                                    parcelId: parcel.plotCode || `P${Date.now()}-${allParcels.length}`,
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
                                    sourceFile: path.relative(directory, gpkgPath)
                                });
                            }
                        }
                    }
                } catch (error) {
                    logger.warn(`Failed to process GeoPackage: ${gpkgPath}`, { error: error.message });
                    // Continue with other files
                }
            }
            
            logger.info('Parsed parcels from GeoPackage files', { 
                totalParcels: allParcels.length,
                fileCount: gpkgFiles.length 
            });
            return allParcels;
        }
        
        // Fall back to shapefile processing if no geopackages found
        const shpFile = files.find(f => f.toLowerCase().endsWith('.shp'));
        if (!shpFile) {
            const fileExtensions = files
                .filter(f => !fs.statSync(path.join(directory, f)).isDirectory())
                .map(f => path.extname(f).toLowerCase())
                .filter(ext => ext)
                .reduce((acc, ext) => {
                    acc[ext] = (acc[ext] || 0) + 1;
                    return acc;
                }, {});
            
            logger.error('Archive format not supported', {
                expectedFormats: ['.shp', '.gpkg'],
                foundExtensions: fileExtensions,
                fileList: files,
                gpkgSearchResults: gpkgFiles
            });
            
            throw new Error(`No .shp or .gpkg file found in archive. Found: ${JSON.stringify(fileExtensions)}`);
        }
        
        // Process shapefile
        const shpPath = path.join(directory, shpFile);
        const dbfFile = files.find(f => f.toLowerCase().endsWith('.dbf'));
        const dbfPath = dbfFile ? path.join(directory, dbfFile) : undefined;
        
        const utm48n = '+proj=utm +zone=48 +datum=WGS84 +units=m +no_defs';
        const wgs84 = '+proj=longlat +datum=WGS84 +no_defs';
        const transform = proj4(utm48n, wgs84);
        
        const parcels = [];
        const source = await open(shpPath, dbfPath);
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
            
            logger.debug('Calculated area for shapefile parcel', {
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
        
        logger.info('Parsed parcels from shape file', { count: parcels.length });
        return parcels;
    }

    transformCoordinates(geometry, transform) {
        if (geometry.type === 'Polygon') {
            return {
                type: 'Polygon',
                coordinates: geometry.coordinates.map((ring) => 
                    ring.map((coord) => transform.forward(coord))
                ),
            };
        } else if (geometry.type === 'MultiPolygon') {
            return {
                type: 'MultiPolygon',
                coordinates: geometry.coordinates.map((polygon) => 
                    polygon.map((ring) => 
                        ring.map((coord) => transform.forward(coord))
                    )
                ),
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
        } else if (!extracted.zone) {
            extracted.zone = 'Zone1';
            extracted.zoneId = '1';
        } else {
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
        } catch (error) {
            logger.warn('Failed to cleanup temporary directory', { error, directory });
        }
    }
}

module.exports = { ShapeFileProcessor };