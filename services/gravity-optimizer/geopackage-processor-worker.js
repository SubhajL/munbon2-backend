#!/usr/bin/env node

/**
 * GeoPackage Processor Worker
 * Processes RID-MS water requirements and manual water level data
 * Runs on EC2 and writes directly to EC2 PostgreSQL database
 */

const { exec } = require('child_process');
const { promisify } = require('util');
const fs = require('fs').promises;
const path = require('path');
const { Client } = require('pg');
const csv = require('csv-parser');
const { createReadStream } = require('fs');
const { pipeline } = require('stream/promises');

const execAsync = promisify(exec);

// Configuration
const config = {
  // Database configuration for EC2
  database: {
    host: '127.0.0.1',
    port: 5432,
    database: 'munbon_dev',
    user: 'postgres',
    password: 'P@ssw0rd123!', // PostgreSQL password from container
    max: 10,
    idleTimeoutMillis: 30000
  },
  
  // File paths
  paths: {
    uploadDir: process.env.UPLOAD_DIR || '/home/ubuntu/geopackage-uploads',
    tempDir: process.env.TEMP_DIR || '/tmp/geopackage-processing',
    processedDir: process.env.PROCESSED_DIR || '/home/ubuntu/geopackage-processed'
  },
  
  // Processing settings
  processing: {
    pollInterval: parseInt(process.env.POLL_INTERVAL || '30000'), // 30 seconds
    batchSize: parseInt(process.env.BATCH_SIZE || '1000'),
    maxRetries: parseInt(process.env.MAX_RETRIES || '3')
  }
};

// Logger
const logger = {
  info: (msg, ...args) => console.log(`[${new Date().toISOString()}] INFO: ${msg}`, ...args),
  error: (msg, ...args) => console.error(`[${new Date().toISOString()}] ERROR: ${msg}`, ...args),
  warn: (msg, ...args) => console.warn(`[${new Date().toISOString()}] WARN: ${msg}`, ...args)
};

class GeoPackageProcessor {
  constructor() {
    this.client = null;
    this.isProcessing = false;
  }

  async initialize() {
    logger.info('Initializing GeoPackage Processor Worker...');
    
    // Create directories if they don't exist
    await this.ensureDirectories();
    
    // Initialize database connection
    await this.connectDatabase();
    
    logger.info('Worker initialized successfully');
  }

  async ensureDirectories() {
    const dirs = Object.values(config.paths);
    for (const dir of dirs) {
      await fs.mkdir(dir, { recursive: true });
    }
    logger.info('Directories ensured');
  }

  async connectDatabase() {
    try {
      this.client = new Client(config.database);
      await this.client.connect();
      logger.info('Connected to PostgreSQL database');
      
      // Test connection
      const result = await this.client.query('SELECT NOW()');
      logger.info('Database connection test successful:', result.rows[0].now);
    } catch (error) {
      logger.error('Failed to connect to database:', error);
      throw error;
    }
  }

  async processGeoPackage(filePath, type) {
    logger.info(`Processing ${type} geopackage:`, filePath);
    
    const fileName = path.basename(filePath);
    const csvPath = path.join(config.paths.tempDir, fileName.replace('.gpkg', '.csv'));
    
    try {
      // Get file stats for debugging
      const stats = await fs.stat(filePath);
      logger.info('GeoPackage file stats:', {
        size: `${(stats.size / 1024 / 1024).toFixed(2)} MB`,
        modified: stats.mtime,
        fileName
      });
      
      // Inspect geopackage structure first
      logger.info('Inspecting GeoPackage structure...');
      const inspection = await this.inspectGeoPackage(filePath);
      logger.info('GeoPackage inspection results:', {
        layers: inspection.layers,
        primaryLayer: inspection.primaryLayer,
        layerDetails: Object.entries(inspection.layerInfo).map(([layer, info]) => ({
          layer,
          geometryType: info.geometryType,
          featureCount: info.featureCount,
          fieldCount: info.fields.length
        }))
      });
      
      // Convert GeoPackage to CSV using ogr2ogr
      logger.info('Converting GeoPackage to CSV...');
      await this.convertToCSV(filePath, csvPath);
      
      // Verify CSV was created
      const csvStats = await fs.stat(csvPath);
      logger.info('CSV file created:', {
        size: `${(csvStats.size / 1024 / 1024).toFixed(2)} MB`,
        path: csvPath
      });
      
      // Process based on type
      logger.info(`Starting ${type} data processing...`);
      if (type === 'ridplan') {
        await this.processRidPlanData(csvPath);
      } else if (type === 'water_level') {
        await this.processWaterLevelData(csvPath);
      }
      
      // Move to processed directory
      const processedPath = path.join(config.paths.processedDir, fileName);
      await fs.rename(filePath, processedPath);
      logger.info('Moved processed file to:', processedPath);
      
      // Clean up temp CSV
      await fs.unlink(csvPath).catch((err) => {
        logger.warn('Failed to clean up temp CSV:', err.message);
      });
      
      logger.info(`✅ Successfully processed ${type} file:`, fileName);
      
    } catch (error) {
      logger.error(`❌ Error processing ${type} file:`, {
        fileName,
        error: error.message,
        stack: error.stack
      });
      throw error;
    }
  }

  async inspectGeoPackage(geopackagePath) {
    logger.info('Inspecting GeoPackage structure:', geopackagePath);
    
    try {
      // Get list of layers
      const { stdout: layersOutput } = await execAsync(
        `ogrinfo -so "${geopackagePath}" | grep "^[0-9]" | cut -d: -f2 | sed 's/^ *//'`
      );
      
      const layers = layersOutput.split('\n').filter(l => l.trim());
      logger.info('Found layers:', layers);
      
      const layerInfo = {};
      
      // Get detailed info for each layer
      for (const layer of layers) {
        if (!layer.trim()) continue;
        
        const { stdout: infoOutput } = await execAsync(
          `ogrinfo -so "${geopackagePath}" "${layer.trim()}"`
        );
        
        // Parse geometry type
        const geomMatch = infoOutput.match(/Geometry: (\w+)/);
        const geometryType = geomMatch ? geomMatch[1] : 'Unknown';
        
        // Parse feature count
        const countMatch = infoOutput.match(/Feature Count: (\d+)/);
        const featureCount = countMatch ? parseInt(countMatch[1]) : 0;
        
        // Parse extent
        const extentMatch = infoOutput.match(/Extent: \(([-\d.]+), ([-\d.]+)\) - \(([-\d.]+), ([-\d.]+)\)/);
        const extent = extentMatch ? {
          minX: parseFloat(extentMatch[1]),
          minY: parseFloat(extentMatch[2]),
          maxX: parseFloat(extentMatch[3]),
          maxY: parseFloat(extentMatch[4])
        } : null;
        
        // Parse fields
        const fields = [];
        const fieldRegex = /^(\w+): (\w+)(?:\((\d+)(?:\.(\d+))?\))?/gm;
        let fieldMatch;
        while ((fieldMatch = fieldRegex.exec(infoOutput)) !== null) {
          fields.push({
            name: fieldMatch[1],
            type: fieldMatch[2],
            width: fieldMatch[3] ? parseInt(fieldMatch[3]) : null,
            precision: fieldMatch[4] ? parseInt(fieldMatch[4]) : null
          });
        }
        
        layerInfo[layer.trim()] = {
          geometryType,
          featureCount,
          extent,
          fields
        };
      }
      
      return {
        layers,
        layerInfo,
        primaryLayer: layers[0] || null
      };
    } catch (error) {
      logger.error('Failed to inspect GeoPackage:', error);
      return {
        layers: [],
        layerInfo: {},
        primaryLayer: null
      };
    }
  }

  async convertToCSV(geopackagePath, csvPath, layerName = null) {
    // Inspect geopackage first if no layer specified
    if (!layerName) {
      const inspection = await this.inspectGeoPackage(geopackagePath);
      layerName = inspection.primaryLayer;
      logger.info('Using primary layer:', layerName);
    }
    
    const cmd = layerName 
      ? `ogr2ogr -f "CSV" -lco GEOMETRY=AS_WKT "${csvPath}" "${geopackagePath}" "${layerName}"`
      : `ogr2ogr -f "CSV" -lco GEOMETRY=AS_WKT "${csvPath}" "${geopackagePath}"`;
    
    try {
      const { stdout, stderr } = await execAsync(cmd);
      if (stderr && !stderr.includes('Warning')) {
        logger.warn('ogr2ogr warning:', stderr);
      }
      logger.info('Converted to CSV successfully');
    } catch (error) {
      logger.error('Failed to convert geopackage to CSV:', error);
      throw error;
    }
  }

  async processRidPlanData(csvPath) {
    logger.info('Processing RID-MS parcels data...');
    
    const parcels = [];
    let count = 0;
    let firstRow = true;
    let columnMapping = {};
    
    // Read CSV file
    await pipeline(
      createReadStream(csvPath),
      csv(),
      async function* (source) {
        for await (const row of source) {
          // On first row, create column mapping
          if (firstRow) {
            const headers = Object.keys(row);
            logger.info('CSV headers found:', headers);
            logger.info('First row sample:', {
              ...row,
              // Truncate long geometry strings for logging
              WKT: row.WKT ? `${row.WKT.substring(0, 50)}...` : undefined,
              wkt: row.wkt ? `${row.wkt.substring(0, 50)}...` : undefined,
              geom: row.geom ? `${row.geom.substring(0, 50)}...` : undefined
            });
            
            columnMapping = this.createColumnMapping(headers);
            logger.info('Column mapping established:', columnMapping);
            firstRow = false;
          }
          
          // Extract values using flexible column mapping
          const getValue = (fieldName) => {
            const colName = columnMapping[fieldName];
            return colName ? row[colName] : null;
          };
          
          // Convert area_rai to hectares
          const areaRai = parseFloat(getValue('area_rai')) || 0;
          const areaHectares = areaRai / 6.25;
          
          parcels.push({
            parcel_seq: getValue('parcel_seq') || getValue('parcel_id') || `RID_${Date.now()}_${count}`,
            zone_area: getValue('zone_area') || getValue('sub_member'),
            area_rai: areaRai,
            area_hectares: areaHectares,
            batch_date: parseInt(getValue('batch_date_int')) || parseInt(getValue('data_date_int')) || 0,
            start_date: parseInt(getValue('start_int')) || parseInt(getValue('start_date_int')) || 0,
            crop_cycle: parseInt(getValue('crop_cycle')) || 0,
            wpet: parseFloat(getValue('wpet')) || 0,
            wprod: parseFloat(getValue('wprod')) || 0,
            age: parseInt(getValue('age')) || 0,
            plant_id: getValue('plant_id') || getValue('crop_type'),
            stage_age: parseInt(getValue('stage_age')) || 0,
            yield_at_mc_kgpr: parseFloat(getValue('yield_at_mc_kgpr')) || parseFloat(getValue('yield_at_m')) || 0,
            season_rain_m3_per_rai: parseFloat(getValue('season_rain_m3_per_rai')) || 0,
            season_irri_m3_per_rai: parseFloat(getValue('season_irri_m3_per_rai')) || parseFloat(getValue('season_irr')) || 0,
            season_water_input_m3_per_rai: parseFloat(getValue('season_water_input_m3_per_rai')) || 0,
            auto_note: getValue('auto_note'),
            geometry_wkt: getValue('geometry_wkt')
          });
          
          // Process in batches
          if (parcels.length >= config.processing.batchSize) {
            logger.info(`Processing batch of ${config.processing.batchSize} parcels (total processed: ${count})`);
            await this.insertRidPlanBatch(parcels.splice(0));
            count += config.processing.batchSize;
          }
        }
      }.bind(this)
    );
    
    // Process remaining parcels
    if (parcels.length > 0) {
      logger.info(`Processing final batch of ${parcels.length} parcels`);
      await this.insertRidPlanBatch(parcels);
      count += parcels.length;
    }
    
    // Log missing columns
    const expectedFields = [
      'parcel_seq', 'zone_area', 'area_rai', 'batch_date_int', 
      'start_int', 'crop_cycle', 'wpet', 'wprod', 'age', 'plant_id',
      'stage_age', 'yield_at_mc_kgpr', 'season_rain_m3_per_rai',
      'season_irri_m3_per_rai', 'season_water_input_m3_per_rai',
      'auto_note', 'geometry_wkt'
    ];
    const missingColumns = expectedFields.filter(field => !columnMapping[field]);
    
    if (missingColumns.length > 0) {
      logger.warn('Missing column mappings:', missingColumns);
    }
    
    logger.info(`✅ Processed ${count} RID-MS parcels`);
  }

  createColumnMapping(headers) {
    const mapping = {};
    
    // Define possible column name variations
    const columnVariations = {
      parcel_seq: ['PARCEL_SEQ', 'parcel_seq', 'ParcelSeq', 'parcelSeq', 'PARCEL_ID', 'parcel_id'],
      zone_area: ['zone_area', 'ZONE_AREA', 'ZoneArea', 'sub_member', 'SUB_MEMBER'],
      area_rai: ['area_rai', 'AREA_RAI', 'AreaRai', 'parcel_are', 'PARCEL_ARE'],
      batch_date_int: ['batch_date_int', 'BATCH_DATE_INT', 'data_date_', 'DATA_DATE', 'data_date_int'],
      start_int: ['start_int', 'START_INT', 'start_date_int', 'START_DATE_INT'],
      crop_cycle: ['crop_cycle', 'CROP_CYCLE', 'CropCycle'],
      wpet: ['wpet', 'WPET'],
      wprod: ['wprod', 'WPROD'],
      age: ['age', 'AGE'],
      plant_id: ['plant_id', 'PLANT_ID', 'PlantId', 'crop_type', 'CROP_TYPE'],
      stage_age: ['stage_age', 'STAGE_AGE', 'StageAge'],
      yield_at_mc_kgpr: ['yield_at_mc_kgpr', 'YIELD_AT_MC_KGPR', 'yield_at_m', 'YIELD', 'yield'],
      season_rain_m3_per_rai: ['season_rain_m3_per_rai', 'SEASON_RAIN_M3_PER_RAI'],
      season_irri_m3_per_rai: ['season_irri_m3_per_rai', 'SEASON_IRRI_M3_PER_RAI', 'season_irr', 'SEASON_IRR'],
      season_water_input_m3_per_rai: ['season_water_input_m3_per_rai', 'SEASON_WATER_INPUT_M3_PER_RAI'],
      auto_note: ['auto_note', 'AUTO_NOTE', 'AutoNote'],
      geometry_wkt: ['WKT', 'wkt', 'geom', 'GEOM', 'geometry', 'GEOMETRY', 'the_geom', 'THE_GEOM']
    };
    
    // Find matching headers
    for (const [field, variations] of Object.entries(columnVariations)) {
      for (const variation of variations) {
        if (headers.includes(variation)) {
          mapping[field] = variation;
          break;
        }
      }
    }
    
    return mapping;
  }

  async insertRidPlanBatch(parcels) {
    const values = [];
    const params = [];
    let paramIndex = 1;
    
    for (const parcel of parcels) {
      // Build properties object with RID attributes
      const properties = {
        ridAttributes: {
          parcelAreaRai: parcel.area_rai,
          dataDateProcess: parcel.batch_date,
          startInt: parcel.start_date,
          wpet: parcel.wpet,
          wprod: parcel.wprod,
          age: parcel.age,
          plantId: parcel.plant_id,
          yieldAtMcKgpr: parcel.yield_at_mc_kgpr,
          seasonRainM3PerRai: parcel.season_rain_m3_per_rai,
          seasonIrrM3PerRai: parcel.season_irri_m3_per_rai,
          seasonWaterInputM3PerRai: parcel.season_water_input_m3_per_rai,
          autoNote: parcel.auto_note,
          stageAge: parcel.stage_age,
          cropCycle: parcel.crop_cycle,
          zoneArea: parcel.zone_area
        },
        source: 'geopackage_processor',
        importDate: new Date().toISOString()
      };
      
      // Map crop type
      const cropType = this.mapCropType(parcel.plant_id);
      
      // Parse planting date from start_date integer (format: YYYYMMDD)
      let plantingDate = null;
      if (parcel.start_date && parcel.start_date > 0) {
        const dateStr = String(parcel.start_date);
        if (dateStr.length === 8) {
          const year = parseInt(dateStr.substring(0, 4));
          const month = parseInt(dateStr.substring(4, 6));
          const day = parseInt(dateStr.substring(6, 8));
          plantingDate = `${year}-${month.toString().padStart(2, '0')}-${day.toString().padStart(2, '0')}`;
        }
      }
      
      // Handle geometry - validate and check if we have WKT
      let geometryClause = 'NULL';
      if (parcel.geometry_wkt) {
        const validation = this.validateGeometry(parcel.geometry_wkt);
        if (validation.isValid) {
          geometryClause = `ST_GeomFromText($${paramIndex++}, 4326)`;
          params.push(validation.wkt);
          logger.debug(`Valid ${validation.geometryType} geometry for parcel ${parcel.parcel_seq}`);
        } else {
          logger.warn(`Invalid geometry for parcel ${parcel.parcel_seq}: ${validation.error}`);
        }
      }
      
      // Build values clause
      values.push(`(
        $${paramIndex++},
        $${paramIndex++},
        $${paramIndex++},
        $${paramIndex++},
        $${paramIndex++},
        $${paramIndex++},
        $${paramIndex++}::jsonb,
        ${geometryClause}
      )`);
      
      params.push(
        parcel.parcel_seq,                    // plot_code
        'RID_FARMER_' + parcel.parcel_seq,    // farmer_id (generated)
        null,                                  // zone_id (will be updated later)
        parcel.area_hectares,                  // area_hectares
        cropType,                              // current_crop_type
        null,                                  // soil_type
        plantingDate,                          // planting_date
        JSON.stringify(properties)             // properties
      );
    }
    
    const query = `
      INSERT INTO gis.agricultural_plots 
      (plot_code, farmer_id, zone_id, area_hectares, 
       current_crop_type, soil_type, planting_date, properties, boundary)
      VALUES ${values.join(',')}
      ON CONFLICT (plot_code) 
      DO UPDATE SET 
        area_hectares = COALESCE(EXCLUDED.area_hectares, agricultural_plots.area_hectares),
        current_crop_type = COALESCE(EXCLUDED.current_crop_type, agricultural_plots.current_crop_type),
        planting_date = COALESCE(EXCLUDED.planting_date, agricultural_plots.planting_date),
        properties = agricultural_plots.properties || EXCLUDED.properties,
        boundary = COALESCE(EXCLUDED.boundary, agricultural_plots.boundary),
        updated_at = NOW()
    `;
    
    try {
      const result = await this.client.query(query, params);
      
      // Count parcels with valid geometry
      const parcelsWithGeometry = parcels.filter(p => p.geometry_wkt && p.geometry_wkt !== '').length;
      
      logger.info(`✅ Inserted/updated batch of ${parcels.length} agricultural plots`, {
        rowsAffected: result.rowCount,
        parcelsWithGeometry,
        parcelsWithoutGeometry: parcels.length - parcelsWithGeometry,
        sampleParcelIds: parcels.slice(0, 3).map(p => p.parcel_seq)
      });
    } catch (error) {
      logger.error('❌ Failed to insert agricultural plots batch:', {
        error: error.message,
        detail: error.detail,
        hint: error.hint,
        code: error.code
      });
      
      // Log sample data that failed
      if (parcels.length > 0) {
        logger.error('Sample failed parcel:', {
          parcel_seq: parcels[0].parcel_seq,
          area_hectares: parcels[0].area_hectares,
          hasGeometry: !!parcels[0].geometry_wkt
        });
      }
      
      throw error;
    }
  }

  validateGeometry(wktString) {
    if (!wktString || wktString === 'NULL' || wktString === '') {
      return { isValid: false, error: 'Empty or null geometry' };
    }
    
    try {
      // Basic WKT validation patterns
      const wktPatterns = {
        POINT: /^POINT\s*\(\s*[-\d.]+\s+[-\d.]+\s*\)$/i,
        LINESTRING: /^LINESTRING\s*\(/i,
        POLYGON: /^POLYGON\s*\(\s*\(/i,
        MULTIPOINT: /^MULTIPOINT\s*\(/i,
        MULTILINESTRING: /^MULTILINESTRING\s*\(/i,
        MULTIPOLYGON: /^MULTIPOLYGON\s*\(\s*\(\s*\(/i,
        GEOMETRYCOLLECTION: /^GEOMETRYCOLLECTION\s*\(/i
      };
      
      // Check if it matches any known geometry type
      let geometryType = null;
      for (const [type, pattern] of Object.entries(wktPatterns)) {
        if (pattern.test(wktString.trim())) {
          geometryType = type;
          break;
        }
      }
      
      if (!geometryType) {
        return { isValid: false, error: 'Unknown geometry type' };
      }
      
      // Basic bracket matching
      const openCount = (wktString.match(/\(/g) || []).length;
      const closeCount = (wktString.match(/\)/g) || []).length;
      
      if (openCount !== closeCount) {
        return { 
          isValid: false, 
          error: `Unmatched parentheses: ${openCount} open, ${closeCount} close` 
        };
      }
      
      // For polygons, check if it has valid structure
      if (geometryType === 'POLYGON' || geometryType === 'MULTIPOLYGON') {
        // Extract coordinates part
        const coordsMatch = wktString.match(/\(\s*\(([\s\S]+)\)\s*\)/);
        if (!coordsMatch) {
          return { isValid: false, error: 'Invalid polygon structure' };
        }
        
        // Check if coordinates are properly formatted
        const coords = coordsMatch[1];
        const pointPattern = /[-\d.]+\s+[-\d.]+/g;
        const points = coords.match(pointPattern);
        
        if (!points || points.length < 3) {
          return { 
            isValid: false, 
            error: 'Polygon must have at least 3 points' 
          };
        }
        
        // Check if polygon is closed (first point equals last point)
        const firstPoint = points[0].trim().split(/\s+/);
        const lastPoint = points[points.length - 1].trim().split(/\s+/);
        
        if (firstPoint[0] !== lastPoint[0] || firstPoint[1] !== lastPoint[1]) {
          logger.warn('Polygon not closed, will be auto-closed by PostGIS');
        }
      }
      
      return { 
        isValid: true, 
        geometryType,
        wkt: wktString.trim()
      };
      
    } catch (error) {
      return { 
        isValid: false, 
        error: `Validation error: ${error.message}` 
      };
    }
  }

  mapCropType(plantId) {
    if (!plantId) return null;
    
    const cropMap = {
      '1': 'rice',
      '2': 'maize',
      '3': 'sugarcane',
      '4': 'cassava',
      'rice': 'rice',
      'maize': 'maize',
      'corn': 'maize',
      'sugarcane': 'sugarcane',
      'cassava': 'cassava'
    };
    
    return cropMap[String(plantId).toLowerCase()] || plantId;
  }

  async processWaterLevelData(csvPath) {
    logger.info('Processing water level data...');
    
    const readings = [];
    let count = 0;
    
    // Read CSV file
    await pipeline(
      createReadStream(csvPath),
      csv(),
      async function* (source) {
        for await (const row of source) {
          // Convert water level from mm to meters
          const waterLevelM = row.water_level_mm ? parseFloat(row.water_level_mm) / 1000.0 : 0;
          
          readings.push({
            location_id: row.crop_id,
            section_id: 'MB-001', // Default section ID
            plot_id: row.project_name,
            water_level_m: waterLevelM,
            reading_date: row.act_date,
            volunteer_name: 'GeoPackage Import',
            geopackage_source: path.basename(csvPath).replace('.csv', '.gpkg'),
            lat: parseFloat(row.lat_y) || 0,
            lon: parseFloat(row.lon_x) || 0,
            notes: `Original water level: ${row.water_level_mm || '0'}mm`
          });
          
          // Process in batches
          if (readings.length >= config.processing.batchSize) {
            await this.insertWaterLevelBatch(readings.splice(0));
            count += config.processing.batchSize;
          }
        }
      }
    );
    
    // Process remaining readings
    if (readings.length > 0) {
      await this.insertWaterLevelBatch(readings);
      count += readings.length;
    }
    
    logger.info(`Processed ${count} water level readings`);
  }

  async insertWaterLevelBatch(readings) {
    const values = readings.map(reading => {
      return `(
        '${reading.location_id}',
        '${reading.section_id}',
        '${reading.plot_id.replace(/'/g, "''")}',
        ${reading.water_level_m},
        '${reading.reading_date}'::date,
        '${reading.volunteer_name}',
        '${reading.geopackage_source}',
        ST_GeomFromText('POINT(${reading.lon} ${reading.lat})', 4326),
        '${reading.notes}'
      )`;
    }).join(',');
    
    const query = `
      INSERT INTO ros_gis.manual_water_level_readings 
      (location_id, section_id, plot_id, water_level_m, reading_date,
       volunteer_name, geopackage_source, coordinates, notes)
      VALUES ${values}
    `;
    
    try {
      await this.client.query(query);
      logger.info(`Inserted batch of ${readings.length} water level readings`);
    } catch (error) {
      logger.error('Failed to insert water level batch:', error);
      throw error;
    }
  }

  async scanForFiles() {
    if (this.isProcessing) {
      logger.info('Already processing, skipping scan');
      return;
    }
    
    this.isProcessing = true;
    
    try {
      const files = await fs.readdir(config.paths.uploadDir);
      
      for (const file of files) {
        if (!file.endsWith('.gpkg')) continue;
        
        const filePath = path.join(config.paths.uploadDir, file);
        
        // Determine file type based on name patterns
        let type = null;
        if (file.includes('ridplan') || file.includes('rice') || file.includes('parcel')) {
          type = 'ridplan';
        } else if (file.includes('water_level') || file.includes('water')) {
          type = 'water_level';
        }
        
        if (type) {
          try {
            await this.processGeoPackage(filePath, type);
          } catch (error) {
            logger.error(`Failed to process ${file}:`, error);
            // Continue with other files
          }
        }
      }
    } catch (error) {
      logger.error('Error scanning for files:', error);
    } finally {
      this.isProcessing = false;
    }
  }

  async start() {
    logger.info('Starting GeoPackage Processor Worker...');
    
    // Initial scan
    await this.scanForFiles();
    
    // Set up periodic scanning
    setInterval(() => {
      this.scanForFiles().catch(error => {
        logger.error('Error in periodic scan:', error);
      });
    }, config.processing.pollInterval);
    
    logger.info(`Worker started, polling every ${config.processing.pollInterval}ms`);
  }

  async shutdown() {
    logger.info('Shutting down worker...');
    
    if (this.client) {
      await this.client.end();
    }
    
    logger.info('Worker shutdown complete');
  }
}

// Main execution
async function main() {
  const processor = new GeoPackageProcessor();
  
  // Handle shutdown signals
  process.on('SIGTERM', async () => {
    logger.info('Received SIGTERM signal');
    await processor.shutdown();
    process.exit(0);
  });
  
  process.on('SIGINT', async () => {
    logger.info('Received SIGINT signal');
    await processor.shutdown();
    process.exit(0);
  });
  
  try {
    await processor.initialize();
    await processor.start();
  } catch (error) {
    logger.error('Fatal error:', error);
    process.exit(1);
  }
}

// Run if called directly
if (require.main === module) {
  main();
}

module.exports = { GeoPackageProcessor };