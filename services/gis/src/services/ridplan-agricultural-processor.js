const fs = require('fs');
const path = require('path');
const AdmZip = require('adm-zip');
const { GeoPackageAPI } = require('@ngageoint/geopackage');
const { logger } = require('../utils/logger');
const { AppDataSource } = require('../config/database');
const { GeoPackageHelper } = require('../utils/geopackage-helper');

class RidplanAgriculturalProcessor {
    constructor() {
        this.tempDir = '/tmp/gis-shape-files';
        this.preserveDir = '/tmp/gis-preserved-data';
        
        // Create directories
        [this.tempDir, this.preserveDir].forEach(dir => {
            if (!fs.existsSync(dir)) {
                fs.mkdirSync(dir, { recursive: true });
            }
        });
    }

    async processShapeFile(options) {
        const uploadDir = path.join(this.tempDir, options.uploadId);
        try {
            // Extract ZIP file
            fs.mkdirSync(uploadDir, { recursive: true });
            const zipPath = path.join(uploadDir, options.fileName);
            fs.writeFileSync(zipPath, options.buffer);
            
            const zip = new AdmZip(zipPath);
            zip.extractAllTo(uploadDir, true);
            logger.info('Extracted shape file archive', { uploadDir });
            
            // Check what folders exist
            const folders = fs.readdirSync(uploadDir).filter(f => 
                fs.statSync(path.join(uploadDir, f)).isDirectory()
            );
            logger.info('Found folders in archive', { folders });
            
            // Preserve data_water_level and data_gistda for later
            await this.preserveDataFolders(uploadDir, options.uploadId);
            
            // Process data_ridplan
            const ridplanData = await this.processRidplanData(uploadDir, options.uploadId);
            
            return ridplanData;
        } finally {
            this.cleanupDirectory(uploadDir);
        }
    }

    async preserveDataFolders(uploadDir, uploadId) {
        const foldersToPreserve = ['data_water_level', 'data_gistda'];
        
        for (const folder of foldersToPreserve) {
            const sourcePath = path.join(uploadDir, folder);
            if (fs.existsSync(sourcePath)) {
                const destPath = path.join(this.preserveDir, uploadId, folder);
                
                // Create destination directory
                fs.mkdirSync(path.dirname(destPath), { recursive: true });
                
                // Copy folder recursively
                this.copyFolderRecursive(sourcePath, destPath);
                
                logger.info('Preserved folder for later processing', { 
                    folder, 
                    uploadId,
                    destination: destPath 
                });
            }
        }
    }

    copyFolderRecursive(source, target) {
        if (!fs.existsSync(target)) {
            fs.mkdirSync(target, { recursive: true });
        }
        
        const files = fs.readdirSync(source);
        files.forEach(file => {
            const sourcePath = path.join(source, file);
            const targetPath = path.join(target, file);
            
            if (fs.statSync(sourcePath).isDirectory()) {
                this.copyFolderRecursive(sourcePath, targetPath);
            } else {
                fs.copyFileSync(sourcePath, targetPath);
            }
        });
    }

    async processRidplanData(uploadDir, uploadId) {
        const parcels = [];
        const ridplanDir = path.join(uploadDir, 'data_ridplan');
        
        if (!fs.existsSync(ridplanDir)) {
            logger.warn('No data_ridplan directory found in upload', { uploadId });
            return { parcels: [] };
        }
        
        // Find all GeoPackage files in data_ridplan
        const gpkgFiles = this.findGeoPackageFiles(ridplanDir);
        logger.info('Found GeoPackage files in data_ridplan', { 
            count: gpkgFiles.length,
            files: gpkgFiles.map(f => path.relative(ridplanDir, f))
        });
        
        for (const gpkgPath of gpkgFiles) {
            let geoPackage = null;
            try {
                logger.info('Processing ridplan GeoPackage', { 
                    file: path.basename(gpkgPath) 
                });
                
                geoPackage = await GeoPackageAPI.open(gpkgPath);
                const tables = geoPackage.getFeatureTables();
                logger.info('Found tables in GeoPackage', { tables });
                
                for (const tableName of tables) {
                    const tableData = await this.extractTableData(geoPackage, tableName);
                    parcels.push(...tableData);
                }
            } catch (error) {
                logger.error('Error processing GeoPackage', { 
                    file: gpkgPath,
                    error: error.message 
                });
            } finally {
                if (geoPackage) {
                    try {
                        geoPackage.close();
                    } catch (e) {
                        // Ignore close errors
                    }
                }
            }
        }
        
        // Save parcels to agricultural_plots table
        if (parcels.length > 0) {
            await this.saveToAgriculturalPlots(parcels, uploadId);
        }
        
        return { parcels };
    }

    findGeoPackageFiles(dir) {
        const gpkgFiles = [];
        
        const searchDir = (currentDir) => {
            const items = fs.readdirSync(currentDir);
            for (const item of items) {
                const fullPath = path.join(currentDir, item);
                const stats = fs.statSync(fullPath);
                
                if (stats.isDirectory()) {
                    searchDir(fullPath);
                } else if (item.toLowerCase().endsWith('.gpkg')) {
                    gpkgFiles.push(fullPath);
                }
            }
        };
        
        searchDir(dir);
        return gpkgFiles;
    }

    async extractTableData(geoPackage, tableName) {
        const parcels = [];
        
        try {
            const featureDao = geoPackage.getFeatureDao(tableName);
            
            // Get table metadata
            const metadata = GeoPackageHelper.getTableMetadata(featureDao);
            logger.info('Processing table with metadata', { 
                tableName,
                metadata
            });
            
            // Extract all rows using helper
            const rows = await GeoPackageHelper.extractAllRows(featureDao);
            
            logger.info('Found rows in table', { 
                tableName,
                rowCount: rows.length
            });
            
            // Process each row
            for (let i = 0; i < rows.length; i++) {
                const rowData = rows[i];
                
                // Log first row for debugging
                if (i === 0) {
                    logger.info('Sample ridplan data', { 
                        tableName,
                        properties: Object.keys(rowData.properties),
                        sampleValues: Object.entries(rowData.properties)
                            .slice(0, 5)
                            .reduce((acc, [k, v]) => ({ ...acc, [k]: v }), {})
                    });
                }
                
                // Map to agricultural plot using helper
                const parcel = GeoPackageHelper.mapToAgriculturalPlot(rowData, tableName);
                if (parcel) {
                    parcels.push(parcel);
                }
            }
        } catch (error) {
            logger.error('Error extracting table data', { 
                tableName,
                error: error.message 
            });
        }
        
        logger.info('Extracted parcels from table', { 
            tableName,
            count: parcels.length 
        });
        
        return parcels;
    }


    async saveToAgriculturalPlots(parcels, uploadId) {
        // Ensure database is initialized
        if (!AppDataSource.isInitialized) {
            await AppDataSource.initialize();
            logger.info('Database connection initialized');
        }
        
        const queryRunner = AppDataSource.createQueryRunner();
        await queryRunner.connect();
        await queryRunner.startTransaction();
        
        let savedCount = 0;
        let errorCount = 0;
        
        try {
            for (const parcel of parcels) {
                try {
                    // Check if we need to get zone_id based on location
                    let zoneId = null;
                    if (parcel.properties.ridAttributes.subMember) {
                        const zoneResult = await queryRunner.query(
                            `SELECT id FROM gis.irrigation_zones 
                             WHERE zone_code = $1 OR zone_name LIKE $2 
                             LIMIT 1`,
                            [
                                `Zone${parcel.properties.ridAttributes.subMember}`,
                                `%${parcel.properties.ridAttributes.subMember}%`
                            ]
                        );
                        
                        if (zoneResult.length > 0) {
                            zoneId = zoneResult[0].id;
                        }
                    }
                    
                    // Insert or update agricultural plot
                    await queryRunner.query(
                        `INSERT INTO gis.agricultural_plots 
                        (plot_code, farmer_id, zone_id, area_hectares, 
                         current_crop_type, soil_type, planting_date, 
                         properties, boundary)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, 
                                ST_GeomFromText('POINT(0 0)', 4326))
                        ON CONFLICT (plot_code) 
                        DO UPDATE SET 
                            farmer_id = COALESCE(EXCLUDED.farmer_id, agricultural_plots.farmer_id),
                            area_hectares = COALESCE(EXCLUDED.area_hectares, agricultural_plots.area_hectares),
                            current_crop_type = COALESCE(EXCLUDED.current_crop_type, agricultural_plots.current_crop_type),
                            soil_type = COALESCE(EXCLUDED.soil_type, agricultural_plots.soil_type),
                            planting_date = COALESCE(EXCLUDED.planting_date, agricultural_plots.planting_date),
                            properties = agricultural_plots.properties || EXCLUDED.properties,
                            updated_at = NOW()`,
                        [
                            parcel.plot_code,
                            parcel.farmer_id,
                            zoneId,
                            parcel.area_hectares,
                            parcel.current_crop_type,
                            parcel.soil_type,
                            parcel.planting_date,
                            JSON.stringify(parcel.properties)
                        ]
                    );
                    
                    savedCount++;
                } catch (parcelError) {
                    logger.error('Error saving parcel', { 
                        plot_code: parcel.plot_code,
                        error: parcelError.message 
                    });
                    errorCount++;
                }
            }
            
            await queryRunner.commitTransaction();
            
            logger.info('Saved parcels to agricultural_plots', { 
                uploadId,
                total: parcels.length,
                saved: savedCount,
                errors: errorCount
            });
        } catch (error) {
            await queryRunner.rollbackTransaction();
            logger.error('Transaction failed', { error: error.message });
            throw error;
        } finally {
            await queryRunner.release();
        }
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

module.exports = { RidplanAgriculturalProcessor };