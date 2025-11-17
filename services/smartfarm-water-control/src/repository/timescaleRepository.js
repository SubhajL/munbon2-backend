const logger = require('../utils/logger');

// Helper: map layer -> column name for moisture
function moistureColumnForLayer(layer = 'surface') {
  return layer === 'deep' ? 'moisture_deep_pct' : 'moisture_surface_pct';
}

class TimescaleRepository {
  constructor(
    pool,
    schemas = {
      planning: 'ros_gis_smartfarm',
      control: 'water_control_smartfarm'
    }
  ) {
    this.pool = pool;
    this.schemas = schemas;
  }

// Get latest sensor reading for a specific sensor
  async getLatestSensorReading(sensorId, sensorType, options = {}) {
    let tableName;
    let valueColumn;

    if (sensorType === 'moisture') {
      tableName = 'moisture_readings';
      const layer = options.moistureLayer || 'surface';
      valueColumn = moistureColumnForLayer(layer);
    } else if (sensorType === 'water_level') {
      tableName = 'water_level_readings';
      valueColumn = 'water_level_cm';
    } else {
      throw new Error(`Unknown sensor type: ${sensorType}`);
    }

    const query = `
      SELECT
        sensor_id,
        ${valueColumn} as value,
        time as timestamp,
        location_lat as lat,
        location_lng as lng
      FROM ${tableName}
      WHERE sensor_id = $1
      ORDER BY time DESC
      LIMIT 1
    `;

    try {
      const result = await this.pool.query(query, [sensorId]);

      if (result.rows.length === 0) {
        return null;
      }

      const row = result.rows[0];
      return {
        sensorId: row.sensor_id,
        value: parseFloat(row.value),
        timestamp: row.timestamp,
        location: {
          lat: row.lat,
          lng: row.lng
        },
        type: sensorType,
        unit: sensorType === 'moisture' ? '%' : 'cm'
      };
    } catch (error) {
      logger.error(
        { error, sensorId, sensorType },
        'Failed to get sensor reading'
      );
      throw error;
    }
  }

  // Convenience: latest moisture reading with layer selection
  async getLatestMoistureReading(sensorId, moistureLayer = 'surface') {
    return this.getLatestSensorReading(sensorId, 'moisture', { moistureLayer });
  }

// Get sensor readings within a time range
  async getSensorHistory(sensorId, sensorType, startDate, endDate, options = {}) {
    let tableName;
    let valueColumn;

    if (sensorType === 'moisture') {
      tableName = 'moisture_readings';
      const layer = options.moistureLayer || 'surface';
      valueColumn = moistureColumnForLayer(layer);
    } else if (sensorType === 'water_level') {
      tableName = 'water_level_readings';
      valueColumn = 'water_level_cm';
    } else {
      throw new Error(`Unknown sensor type: ${sensorType}`);
    }

    const query = `
      SELECT
        sensor_id,
        ${valueColumn} as value,
        time as timestamp,
        location_lat as lat,
        location_lng as lng
      FROM ${tableName}
      WHERE sensor_id = $1
        AND time >= $2
        AND time <= $3
      ORDER BY time ASC
    `;

    try {
      const result = await this.pool.query(query, [
        sensorId,
        startDate,
        endDate
      ]);

      return result.rows.map((row) => ({
        sensorId: row.sensor_id,
        value: parseFloat(row.value),
        timestamp: row.timestamp,
        location: {
          lat: row.lat,
          lng: row.lng
        },
        type: sensorType,
        unit: sensorType === 'moisture' ? '%' : 'cm'
      }));
    } catch (error) {
      logger.error(
        { error, sensorId, sensorType },
        'Failed to get sensor history'
      );
      throw error;
    }
  }

  // Check sensor health by getting last update time
  async checkSensorHealth(sensorId, sensorType) {
    const reading = await this.getLatestSensorReading(sensorId, sensorType);

    if (!reading) {
      return {
        sensorId,
        healthy: false,
        reason: 'No data available'
      };
    }

    const age = Date.now() - new Date(reading.timestamp).getTime();
    const maxAge = 15 * 60 * 1000; // 15 minutes

    if (age > maxAge) {
      return {
        sensorId,
        healthy: false,
        reason: 'Stale data',
        lastReading: reading.timestamp
      };
    }

    return {
      sensorId,
      healthy: true,
      lastReading: reading.timestamp
    };
  }

  // Save water demand to planning schema
  async saveWaterDemand(demand) {
    const query = `
      INSERT INTO ${this.schemas.planning}.daily_water_demands
      (plot_id, date, demand_m3, crop_type, growth_stage, et0, kc, effective_rainfall)
      VALUES ($1, $2::date, $3, $4, $5, $6, $7, $8)
      ON CONFLICT (plot_id, date)
      DO UPDATE SET
        demand_m3 = EXCLUDED.demand_m3,
        crop_type = EXCLUDED.crop_type,
        growth_stage = EXCLUDED.growth_stage,
        et0 = EXCLUDED.et0,
        kc = EXCLUDED.kc,
        effective_rainfall = EXCLUDED.effective_rainfall,
        updated_at = CURRENT_TIMESTAMP
    `;

    try {
      await this.pool.query(query, [
        demand.plotId,
        demand.date,
        demand.demandCubicMeters,
        demand.cropType,
        demand.growthStage,
        demand.et0,
        demand.kc,
        demand.effectiveRainfall
      ]);
    } catch (error) {
      logger.error({ error, demand }, 'Failed to save water demand');
      throw error;
    }
  }

  // Get planned water demand for a plot
  async getPlannedDemand(plotId, date) {
    const query = `
      SELECT demand_m3
      FROM ${this.schemas.planning}.daily_water_demands
      WHERE plot_id = $1 AND date = $2::date
    `;

    try {
      const result = await this.pool.query(query, [plotId, date]);
      return result.rows.length > 0 ? result.rows[0].demand_m3 : 0;
    } catch (error) {
      logger.error({ error, plotId, date }, 'Failed to get planned demand');
      return 0;
    }
  }

  // Save daily progress
  async saveDailyProgress(
    plotId,
    date,
    plannedDemand,
    actualUsage,
    efficiency
  ) {
    const query = `
      INSERT INTO ${this.schemas.planning}.daily_progress
      (plot_id, date, planned_demand, actual_usage, efficiency, last_updated)
      VALUES ($1, $2::date, $3, $4, $5, CURRENT_TIMESTAMP)
      ON CONFLICT (plot_id, date)
      DO UPDATE SET
        planned_demand = EXCLUDED.planned_demand,
        actual_usage = EXCLUDED.actual_usage,
        efficiency = EXCLUDED.efficiency,
        last_updated = CURRENT_TIMESTAMP
    `;

    try {
      await this.pool.query(query, [
        plotId,
        date,
        plannedDemand,
        actualUsage,
        efficiency
      ]);
    } catch (error) {
      logger.error({ error, plotId }, 'Failed to save daily progress');
      throw error;
    }
  }

  // Record irrigation cycle
  async recordIrrigationCycle(cycle) {
    const query = `
      INSERT INTO ${this.schemas.control}.water_balance
      (plot_id, valve_name, start_time, end_time, volume_liters, control_mode, trigger_value)
      VALUES ($1, $2, $3, $4, $5, $6, $7)
    `;

    try {
      await this.pool.query(query, [
        cycle.plotId,
        cycle.valveName,
        cycle.startTime,
        cycle.endTime,
        cycle.volumeLiters,
        cycle.controlMode,
        cycle.triggerValue || 0
      ]);
    } catch (error) {
      logger.error({ error, cycle }, 'Failed to record irrigation cycle');
      throw error;
    }
  }

  // Update valve status
  async updateValveStatus(plotId, valveName, status, timestamp) {
    const query = `
      INSERT INTO ${this.schemas.control}.valve_status
      (plot_id, valve_name, status, timestamp)
      VALUES ($1, $2, $3, $4)
    `;

    try {
      await this.pool.query(query, [plotId, valveName, status, timestamp]);
    } catch (error) {
      logger.error({ error, plotId, status }, 'Failed to update valve status');
      // Non-critical, don't throw
    }
  }

  // Get daily water balance
  async getDailyWaterBalance(plotId, startDate, endDate) {
    const query = `
      SELECT
        COALESCE(SUM(volume_liters), 0) as total_usage_liters,
        COALESCE(COUNT(*), 0) as number_of_cycles,
        COALESCE(AVG(EXTRACT(EPOCH FROM (end_time - start_time)) / 60), 0) as average_duration_minutes
      FROM ${this.schemas.control}.water_balance
      WHERE plot_id = $1
        AND start_time >= $2
        AND start_time <= $3
    `;

    try {
      const result = await this.pool.query(query, [plotId, startDate, endDate]);
      return (
        result.rows[0] || {
          total_usage_liters: 0,
          number_of_cycles: 0,
          average_duration_minutes: 0
        }
      );
    } catch (error) {
      logger.error({ error, plotId }, 'Failed to get daily water balance');
      throw error;
    }
  }

  // Get aggregated usage metrics
  async getAggregatedUsageMetrics(startDate, endDate) {
    const query = `
      SELECT
        plot_id,
        SUM(volume_liters) as total_volume,
        COUNT(*) as total_cycles,
        AVG(EXTRACT(EPOCH FROM (end_time - start_time)) / 60) as avg_cycle_duration
      FROM ${this.schemas.control}.water_balance
      WHERE start_time >= $1 AND start_time <= $2
      GROUP BY plot_id
      ORDER BY plot_id
    `;

    try {
      const result = await this.pool.query(query, [startDate, endDate]);
      return result.rows.map((row) => ({
        plotId: row.plot_id,
        totalVolumeLiters: parseInt(row.total_volume),
        totalCycles: parseInt(row.total_cycles),
        avgCycleDurationMinutes: parseFloat(row.avg_cycle_duration)
      }));
    } catch (error) {
      logger.error({ error }, 'Failed to get aggregated usage metrics');
      throw error;
    }
  }

  // Get all control modes from database (reads from plot_configurations)
  async getControlModes() {
    const query = `
      SELECT plot_id, control_mode, crop_type
      FROM ${this.schemas.control}.plot_configurations
      ORDER BY plot_id
    `;

    try {
      const result = await this.pool.query(query, []);
      return result.rows.map((row) => ({
        plotId: row.plot_id,
        controlMode: row.control_mode,
        cropType: row.crop_type
      }));
    } catch (error) {
      logger.error({ error }, 'Failed to get control modes');
      throw error;
    }
  }

  // Get control mode for a specific plot (reads from plot_configurations)
  async getControlMode(plotId) {
    const query = `
      SELECT plot_id, control_mode, crop_type
      FROM ${this.schemas.control}.plot_configurations
      WHERE plot_id = $1
    `;

    try {
      const result = await this.pool.query(query, [plotId]);
      if (result.rows.length === 0) {
        return null;
      }
      const row = result.rows[0];
      return {
        plotId: row.plot_id,
        controlMode: row.control_mode,
        cropType: row.crop_type
      };
    } catch (error) {
      logger.error({ error, plotId }, 'Failed to get control mode');
      throw error;
    }
  }

  // ============================================================================
  // Enriched views for plot configurations and mappings
  // ============================================================================

  async getEnrichedPlotConfigurations(db) {
    const query = `
      SELECT plot_id, crop_type, control_mode, area_rai, valve_id
      FROM ${this.schemas.control}.v_plot_configurations_enriched
      ORDER BY plot_id
    `;
    const result = await db.query(query, []);
    return result.rows;
  }

  async getEnrichedSensorMappings(db) {
    const query = `
      SELECT plot_id, sensor_type, sensor_id
      FROM ${this.schemas.control}.v_sensor_plot_mapping_enriched
      ORDER BY plot_id, sensor_type
    `;
    const result = await db.query(query, []);
    return result.rows;
  }

  // ============================================================================
  // PLOT CONFIGURATION METHODS (crop type + control mode)
  // ============================================================================

  async getAllPlotConfigurations() {
    const query = `
      SELECT
        plot_id,
        crop_type,
        control_mode,
        created_at,
        updated_at,
        updated_by,
        notes
      FROM ${this.schemas.control}.plot_configurations
      ORDER BY plot_id
    `;

    try {
      const result = await this.pool.query(query, []);
      return result.rows.map((row) => ({
        plotId: row.plot_id,
        cropType: row.crop_type,
        controlMode: row.control_mode,
        createdAt: row.created_at,
        updatedAt: row.updated_at,
        updatedBy: row.updated_by,
        notes: row.notes
      }));
    } catch (error) {
      logger.error({ error }, 'Failed to get all plot configurations');
      throw error;
    }
  }

  async getPlotConfiguration(plotId) {
    const query = `
      SELECT
        plot_id,
        crop_type,
        control_mode,
        created_at,
        updated_at,
        updated_by,
        notes
      FROM ${this.schemas.control}.plot_configurations
      WHERE plot_id = $1
    `;

    try {
      const result = await this.pool.query(query, [plotId]);
      if (result.rows.length === 0) {
        return null;
      }
      const row = result.rows[0];
      return {
        plotId: row.plot_id,
        cropType: row.crop_type,
        controlMode: row.control_mode,
        createdAt: row.created_at,
        updatedAt: row.updated_at,
        updatedBy: row.updated_by,
        notes: row.notes
      };
    } catch (error) {
      logger.error({ error, plotId }, 'Failed to get plot configuration');
      throw error;
    }
  }

  async upsertPlotConfiguration({
    plotId,
    cropType,
    controlMode,
    updatedBy,
    notes
  }) {
    const query = `
      INSERT INTO ${this.schemas.control}.plot_configurations
        (plot_id, crop_type, control_mode, updated_by, notes)
      VALUES ($1, $2, $3, $4, $5)
      ON CONFLICT (plot_id) DO UPDATE SET
        crop_type = EXCLUDED.crop_type,
        control_mode = EXCLUDED.control_mode,
        updated_by = EXCLUDED.updated_by,
        notes = EXCLUDED.notes,
        updated_at = NOW()
      RETURNING
        plot_id, crop_type, control_mode,
        created_at, updated_at, updated_by, notes
    `;

    try {
      const result = await this.pool.query(query, [
        plotId,
        cropType,
        controlMode,
        updatedBy,
        notes
      ]);
      const row = result.rows[0];
      return {
        plotId: row.plot_id,
        cropType: row.crop_type,
        controlMode: row.control_mode,
        createdAt: row.created_at,
        updatedAt: row.updated_at,
        updatedBy: row.updated_by,
        notes: row.notes
      };
    } catch (error) {
      logger.error(
        { error, plotId, cropType, controlMode },
        'Failed to upsert plot configuration'
      );
      throw error;
    }
  }

  async batchUpsertPlotConfigurations(configurations) {
    const client = await this.pool.connect();
    try {
      await client.query('BEGIN');

      const results = [];
      for (const config of configurations) {
        const query = `
          INSERT INTO ${this.schemas.control}.plot_configurations
            (plot_id, crop_type, control_mode, updated_by, notes)
          VALUES ($1, $2, $3, $4, $5)
          ON CONFLICT (plot_id) DO UPDATE SET
            crop_type = EXCLUDED.crop_type,
            control_mode = EXCLUDED.control_mode,
            updated_by = EXCLUDED.updated_by,
            notes = EXCLUDED.notes,
            updated_at = NOW()
          RETURNING
            plot_id, crop_type, control_mode,
            created_at, updated_at, updated_by, notes
        `;

        const result = await client.query(query, [
          config.plotId,
          config.cropType,
          config.controlMode,
          config.updatedBy,
          config.notes || null
        ]);

        const row = result.rows[0];
        results.push({
          plotId: row.plot_id,
          cropType: row.crop_type,
          controlMode: row.control_mode,
          createdAt: row.created_at,
          updatedAt: row.updated_at,
          updatedBy: row.updated_by,
          notes: row.notes
        });
      }

      await client.query('COMMIT');
      return results;
    } catch (error) {
      await client.query('ROLLBACK');
      logger.error({ error }, 'Failed to batch upsert plot configurations');
      throw error;
    } finally {
      client.release();
    }
  }

// Get control thresholds for a plot
  async getControlThresholds(db, plotId) {
    const query = `
      SELECT
        plot_id,
        moisture_lower_threshold,
        moisture_upper_threshold,
        water_level_lower_threshold,
        water_level_upper_threshold,
        COALESCE(moisture_layer, 'surface') AS moisture_layer
      FROM ${this.schemas.control}.control_thresholds
      WHERE plot_id = $1
    `;

    try {
      const result = await db.query(query, [plotId]);

      if (result.rows.length === 0) {
        return null;
      }

      const row = result.rows[0];
      return {
        plotId: row.plot_id,
        moistureLowerThreshold: parseFloat(row.moisture_lower_threshold),
        moistureUpperThreshold: parseFloat(row.moisture_upper_threshold),
        waterLevelLowerThreshold: parseFloat(row.water_level_lower_threshold),
        waterLevelUpperThreshold: parseFloat(row.water_level_upper_threshold),
        moistureLayer: row.moisture_layer || 'surface'
      };
    } catch (error) {
      logger.error({ error, plotId }, 'Failed to get control thresholds');
      throw error;
    }
  }

  // Get sensor to plot mapping
  async getSensorPlotMapping(db, sensorId) {
    const query = `
      SELECT
        plot_id,
        sensor_type
      FROM ${this.schemas.control}.sensor_plot_mapping
      WHERE sensor_id = $1
    `;

    try {
      const result = await db.query(query, [sensorId]);

      if (result.rows.length === 0) {
        return null;
      }

      const row = result.rows[0];
      return {
        plotId: row.plot_id,
        sensorType: row.sensor_type
      };
    } catch (error) {
      logger.error({ error, sensorId }, 'Failed to get sensor plot mapping');
      throw error;
    }
  }

  // Find plot by coordinates using PostGIS spatial query
  async findPlotByCoordinates(db, longitude, latitude) {
    const query = `
      SELECT plot_id
      FROM ros_gis_smartfarm.plot_boundaries
      WHERE ST_Contains(
        geom,
        ST_SetSRID(ST_MakePoint($1, $2), 4326)
      )
      LIMIT 1
    `;

    try {
      const result = await db.query(query, [longitude, latitude]);

      if (result.rows.length === 0) {
        return null;
      }

      return result.rows[0].plot_id;
    } catch (error) {
      logger.error(
        { error, longitude, latitude },
        'Failed to find plot by coordinates'
      );
      throw error;
    }
  }

  // Upsert sensor-to-plot mapping
  async upsertSensorPlotMapping(db, { sensorId, plotId, sensorType }) {
    const query = `
      INSERT INTO ${this.schemas.control}.sensor_plot_mapping
        (sensor_id, plot_id, sensor_type, updated_at)
      VALUES ($1, $2, $3, NOW())
      ON CONFLICT (sensor_id)
      DO UPDATE SET
        plot_id = EXCLUDED.plot_id,
        sensor_type = EXCLUDED.sensor_type,
        updated_at = NOW()
      RETURNING plot_id
    `;

    try {
      const result = await db.query(query, [sensorId, plotId, sensorType]);
      return result.rows[0].plot_id;
    } catch (error) {
      logger.error(
        { error, sensorId, plotId, sensorType },
        'Failed to upsert sensor plot mapping'
      );
      throw error;
    }
  }

  // Get valve state for a plot
  async getValveState(db, plotId) {
    const query = `
      SELECT
        current_state,
        last_changed_at,
        last_change_reason
      FROM ${this.schemas.control}.valve_states
      WHERE plot_id = $1
    `;

    try {
      const result = await db.query(query, [plotId]);

      if (result.rows.length === 0) {
        return {
          currentState: 'OFF',
          lastChangedAt: null,
          lastChangeReason: null
        };
      }

      const row = result.rows[0];
      return {
        currentState: row.current_state,
        lastChangedAt: row.last_changed_at,
        lastChangeReason: row.last_change_reason
      };
    } catch (error) {
      logger.error({ error, plotId }, 'Failed to get valve state');
      throw error;
    }
  }

  // Update valve state for a plot (upsert)
  async updateValveState(db, plotId, newState, reason) {
    const query = `
      INSERT INTO ${this.schemas.control}.valve_states
        (plot_id, current_state, last_changed_at, last_change_reason)
      VALUES
        ($1, $2, NOW(), $3)
      ON CONFLICT (plot_id)
      DO UPDATE SET
        current_state = EXCLUDED.current_state,
        last_changed_at = EXCLUDED.last_changed_at,
        last_change_reason = EXCLUDED.last_change_reason,
        updated_at = NOW()
    `;

    try {
      await db.query(query, [plotId, newState, reason]);
      return true;
    } catch (error) {
      logger.error(
        { error, plotId, newState, reason },
        'Failed to update valve state'
      );
      throw error;
    }
  }

  // Delete stale sensor readings from other plots (sensor moved)
  async deleteStaleReadingsForSensor(
    db,
    { sensorId, sensorType, currentPlotId }
  ) {
    const query = `
      DELETE FROM ${this.schemas.control}.sensor_plot_readings
      WHERE sensor_id = $1 
        AND sensor_type = $2 
        AND plot_id != $3
      RETURNING plot_id
    `;

    try {
      const result = await db.query(query, [
        sensorId,
        sensorType,
        currentPlotId
      ]);
      return result.rows.map((row) => row.plot_id);
    } catch (error) {
      logger.error(
        { error, sensorId, sensorType, currentPlotId },
        'Failed to delete stale sensor readings'
      );
      throw error;
    }
  }

// Get all fresh sensor readings for a given plot and sensor type
  // Returns array of {sensorId, value, timestamp}
  async getFreshSensorReadingsForPlot(db, { plotId, sensorType, moistureLayer = 'surface' }) {
    // Freshness window: water_level = 4 hours, moisture = 30 mins
    const freshnessWindowMs =
      sensorType === 'water_level' ? 4 * 60 * 60 * 1000 : 30 * 60 * 1000;

    // Query sensor_plot_mapping to find all sensors mapped to this plot+type
    const mappingQuery = `
      SELECT sensor_id
      FROM ${this.schemas.control}.sensor_plot_mapping
      WHERE plot_id = $1 AND sensor_type = $2
    `;

    try {
      const mappingResult = await db.query(mappingQuery, [plotId, sensorType]);
      const sensorIds = mappingResult.rows.map((row) => row.sensor_id);

      if (sensorIds.length === 0) {
        return [];
      }

      // Get latest reading from timescale for each mapped sensor
      const tableName =
        sensorType === 'moisture' ? 'moisture_readings' : 'water_level_readings';
      const valueColumn =
        sensorType === 'moisture'
          ? moistureColumnForLayer(moistureLayer)
          : 'water_level_cm';

      // Use DISTINCT ON to get latest reading per sensor
      const readingsQuery = `
        SELECT DISTINCT ON (sensor_id)
          sensor_id,
          ${valueColumn} as value,
          time as timestamp
        FROM ${tableName}
        WHERE sensor_id = ANY($1)
          AND time >= NOW() - INTERVAL '${freshnessWindowMs} milliseconds'
        ORDER BY sensor_id, time DESC
      `;

      const readingsResult = await db.query(readingsQuery, [sensorIds]);

      return readingsResult.rows.map((row) => ({
        sensorId: row.sensor_id,
        value: parseFloat(row.value),
        timestamp: row.timestamp
      }));
    } catch (error) {
      logger.error(
        { error, plotId, sensorType },
        'Failed to get fresh sensor readings for plot'
      );
      throw error;
    }
  }

// Get latest moisture readings for a set of sensors (freshness window)
  async getLatestMoistureReadings(db, sensorIds, freshnessWindowMs = 30 * 60 * 1000, moistureLayer = 'surface') {
    if (!Array.isArray(sensorIds) || sensorIds.length === 0) return [];
    const valueColumn = moistureColumnForLayer(moistureLayer);
    const readingsQuery = `
      SELECT DISTINCT ON (sensor_id)
        sensor_id,
        ${valueColumn} as value,
        time as timestamp
      FROM moisture_readings
      WHERE sensor_id = ANY($1)
        AND time >= NOW() - INTERVAL '${freshnessWindowMs} milliseconds'
      ORDER BY sensor_id, time DESC
    `;
    const result = await db.query(readingsQuery, [sensorIds]);
    return result.rows.map((row) => ({
      sensorId: row.sensor_id,
      value: parseFloat(row.value),
      timestamp: row.timestamp
    }));
  }

  // Upsert latest sensor reading per plot and sensor_type
  // Supports aggregated readings with contributing sensor IDs
  async upsertSensorPlotReading(db, reading) {
    const query = `
      INSERT INTO ${this.schemas.control}.sensor_plot_readings
        (plot_id, sensor_id, sensor_type, reading_value, units, updated_at, contributing_sensor_ids)
      VALUES ($1, $2, $3, $4, $5, $6, $7)
      ON CONFLICT (plot_id, sensor_type)
      DO UPDATE SET
        sensor_id = EXCLUDED.sensor_id,
        reading_value = EXCLUDED.reading_value,
        units = EXCLUDED.units,
        updated_at = EXCLUDED.updated_at,
        contributing_sensor_ids = EXCLUDED.contributing_sensor_ids
    `;
    try {
      await db.query(query, [
        reading.plotId,
        reading.sensorId,
        reading.sensorType,
        reading.value,
        reading.units,
        reading.timestamp || new Date(),
        reading.contributingSensorIds || null
      ]);
    } catch (error) {
      logger.error({ error, reading }, 'Failed to upsert sensor_plot_readings');
      throw error;
    }
  }

  // Log a control decision to audit trail
  async logControlDecision(db, decision) {
    const query = `
      INSERT INTO ${this.schemas.control}.control_decisions_log
        (plot_id, sensor_id, sensor_type, action, reason,
         sensor_value, lower_threshold, upper_threshold,
         previous_state, new_state, valve_command_sent)
      VALUES
        ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
      RETURNING id
    `;

    try {
      const result = await db.query(query, [
        decision.plotId,
        decision.sensorId,
        decision.sensorType,
        decision.action,
        decision.reason,
        decision.sensorValue,
        decision.lowerThreshold,
        decision.upperThreshold,
        decision.previousState || null,
        decision.newState || null,
        decision.valveCommandSent || false
      ]);

      return parseInt(result.rows[0].id, 10);
    } catch (error) {
      logger.error({ error, decision }, 'Failed to log control decision');
      throw error;
    }
  }

  // Update decision log with valve command result
  async updateDecisionLogResult(db, logId, success, errorMessage = null) {
    const query = `
      UPDATE ${this.schemas.control}.control_decisions_log
      SET
        valve_command_succeeded = $2,
        valve_command_error = $3
      WHERE id = $1
    `;

    try {
      await db.query(query, [logId, success, errorMessage]);
    } catch (error) {
      logger.error(
        { error, logId, success, errorMessage },
        'Failed to update decision log result'
      );
      throw error;
    }
  }

  async getAreaRai(plotId) {
    const q = `
      SELECT area_rai
      FROM ${this.schemas.control}.v_plot_configurations_enriched
      WHERE plot_id = $1
    `;
    const { rows } = await this.pool.query(q, [plotId]);
    if (!rows.length) throw new Error(`area_rai not found for plot ${plotId}`);
    return parseFloat(rows[0].area_rai);
  }

  async getPlantingDate(plotId) {
    const q = `
      SELECT planting_date
      FROM ${this.schemas.control}.plot_configurations
      WHERE plot_id = $1
    `;
    const { rows } = await this.pool.query(q, [plotId]);
    if (!rows.length)
      throw new Error(`planting_date not found for plot ${plotId}`);
    return new Date(rows[0].planting_date);
  }

  async getKcFromRosSmartfarm(cropType, cropWeek) {
    // Use crop_ros_mapping to translate specific crop variety to standardized ros_type
    const q = `
      SELECT kc.kc_value 
      FROM ros_smartfarm.kc_weekly kc
      JOIN ros_smartfarm.crop_ros_mapping crm ON kc.ros_type = crm.ros_type
      WHERE crm.crop_type = $1 AND kc.crop_week = $2
      LIMIT 1
    `;
    const { rows } = await this.pool.query(q, [cropType, cropWeek]);

    // If not found, try to extract first crop from multi-crop string (e.g., "ทุเรียน กล้วย" -> "ทุเรียน")
    if (!rows.length) {
      const firstCrop = cropType.split(' ')[0];
      if (firstCrop !== cropType) {
        const { rows: retryRows } = await this.pool.query(q, [
          firstCrop,
          cropWeek
        ]);
        if (retryRows.length) return parseFloat(retryRows[0].kc_value);
      }
      throw new Error(
        `kc not found for crop_type "${cropType}" week ${cropWeek}`
      );
    }

    return parseFloat(rows[0].kc_value);
  }

  async getEt0FromRosSmartfarm(
    calendarWeek,
    calendarYear,
    aosStation,
    province
  ) {
    const q = `
      SELECT eto_value FROM ros_smartfarm.eto_weekly
      WHERE aos_station = $1 AND province = $2 AND calendar_week = $3 AND calendar_year = $4
    `;
    const { rows } = await this.pool.query(q, [
      aosStation,
      province,
      calendarWeek,
      calendarYear
    ]);
    if (!rows.length)
      throw new Error(`et0 not found for week ${calendarWeek}/${calendarYear}`);
    return parseFloat(rows[0].eto_value);
  }

  async getEffectiveRainfallFromRosSmartfarm(zoneId, weekNumber, year) {
    const q = `
      SELECT effective_rainfall_mm FROM ros_smartfarm.weekly_effective_rainfall
      WHERE zone_id = $1 AND week_number = $2 AND year = $3
    `;
    const { rows } = await this.pool.query(q, [zoneId, weekNumber, year]);
    if (!rows.length) return 0;
    return parseFloat(rows[0].effective_rainfall_mm);
  }

  // ============================================================================
  // OUTBOX PATTERN METHODS
  // ============================================================================

  async fetchUnprocessedOutboxEntries(db, limit = 100) {
    const query = `
      SELECT
        id,
        sensor_id,
        sensor_type,
        value,
        timestamp,
        location_lat,
        location_lng,
        created_at,
        processed_at
      FROM ${this.schemas.control}.sensor_readings_outbox
      WHERE processed_at IS NULL
      ORDER BY created_at ASC
      LIMIT $1
    `;

    try {
      const result = await db.query(query, [limit]);
      return result.rows.map((row) => ({
        id: row.id,
        sensorId: row.sensor_id,
        sensorType: row.sensor_type,
        value: parseFloat(row.value),
        timestamp: row.timestamp,
        locationLat: row.location_lat,
        locationLng: row.location_lng,
        createdAt: row.created_at,
        processedAt: row.processed_at
      }));
    } catch (error) {
      logger.error(
        { error, limit },
        'Failed to fetch unprocessed outbox entries'
      );
      throw error;
    }
  }

  async markOutboxEntryProcessed(db, outboxId, processedAt = new Date()) {
    const query = `
      UPDATE ${this.schemas.control}.sensor_readings_outbox
      SET processed_at = $2
      WHERE id = $1
    `;

    try {
      await db.query(query, [outboxId, processedAt]);
    } catch (error) {
      logger.error(
        { error, outboxId, processedAt },
        'Failed to mark outbox entry as processed'
      );
      throw error;
    }
  }

  async insertOutboxEntry(db, { sensorId, sensorType, value, timestamp }) {
    const query = `
      INSERT INTO ${this.schemas.control}.sensor_readings_outbox
        (sensor_id, sensor_type, value, timestamp)
      VALUES ($1, $2, $3, $4)
      RETURNING id
    `;

    try {
      const result = await db.query(query, [
        sensorId,
        sensorType,
        value,
        timestamp
      ]);
      return result.rows[0].id;
    } catch (error) {
      logger.error(
        { error, sensorId, sensorType, value, timestamp },
        'Failed to insert outbox entry'
      );
      throw error;
    }
  }

  async deleteProcessedOutboxEntries(db, olderThanDate) {
    const query = `
      DELETE FROM ${this.schemas.control}.sensor_readings_outbox
      WHERE processed_at IS NOT NULL
        AND processed_at < $1
    `;

    try {
      const result = await db.query(query, [olderThanDate]);
      return result.rowCount || 0;
    } catch (error) {
      logger.error(
        { error, olderThanDate },
        'Failed to delete processed outbox entries'
      );
      throw error;
    }
  }

  async getPersistentlyZeroMoistureSensors({ days = 7, epsilon = 1.0 } = {}) {
    const query = `
      WITH windowed AS (
        SELECT sensor_id,
               MAX(moisture_surface_pct) AS max_value
        FROM moisture_readings
        WHERE time >= NOW() - INTERVAL '${days} days'
        GROUP BY sensor_id
      )
      SELECT sensor_id
      FROM windowed
      WHERE max_value <= $1
    `;
    const result = await this.pool.query(query, [epsilon]);
    return result.rows.map((r) => r.sensor_id);
  }

  async deactivateSensorsTx({ sensorIds = [], reason = 'deactivated', performedBy = 'system' } = {}) {
    if (!Array.isArray(sensorIds) || sensorIds.length === 0) return { deactivated: 0, removed: 0 };
    await this.pool.query('BEGIN');
    try {
      const insertSql = `
        INSERT INTO ${this.schemas.control}.deactivated_sensors (sensor_id, reason, performed_by, deactivated_at)
        SELECT UNNEST($1::text[]), $2, $3, NOW()
        ON CONFLICT (sensor_id) DO UPDATE SET reason = EXCLUDED.reason, performed_by = EXCLUDED.performed_by, deactivated_at = NOW()
      `;
      const ins = await this.pool.query(insertSql, [sensorIds, reason, performedBy]);
      const deleteSql = `
        DELETE FROM ${this.schemas.control}.sensor_plot_mapping
        WHERE sensor_id = ANY($1)
      `;
      const del = await this.pool.query(deleteSql, [sensorIds]);
      await this.pool.query('COMMIT');
      return { deactivated: ins.rowCount || 0, removed: del.rowCount || 0 };
    } catch (e) {
      await this.pool.query('ROLLBACK');
      throw e;
    }
  }

  async getLatestWLGpsPerSensor({ maxSensors = 1000 } = {}) {
    const query = `
      SELECT DISTINCT ON (sensor_id)
        sensor_id,
        location_lat,
        location_lng,
        time
      FROM public.water_level_readings
      WHERE location_lat IS NOT NULL AND location_lng IS NOT NULL
      ORDER BY sensor_id, time DESC
      LIMIT $1
    `;
    const result = await this.pool.query(query, [maxSensors]);
    return result.rows;
  }

  async upsertWLSensorMapping({ sensorId, plotId }) {
    return this.upsertSensorPlotMapping(this.pool, { sensorId, plotId, sensorType: 'water_level' });
  }

  async deleteLegacyWLSfMappings() {
    const q = `
      DELETE FROM ${this.schemas.control}.sensor_plot_mapping
      WHERE sensor_id LIKE 'WL_SF%'
    `;
    const res = await this.pool.query(q);
    return res.rowCount || 0;
  }

  async getOutboxBacklogCount(db) {
    const query = `
      SELECT COUNT(*) as count
      FROM ${this.schemas.control}.sensor_readings_outbox
      WHERE processed_at IS NULL
    `;

    try {
      const result = await db.query(query);
      return parseInt(result.rows[0].count, 10);
    } catch (error) {
      logger.error({ error }, 'Failed to get outbox backlog count');
      throw error;
    }
  }

  async close() {
    await this.pool.end();
  }

  // Valve mapping (control DB) - fetch all plot→valve rows
  async getAllValvePlotMappings(db = this.pool) {
    const query = `
      SELECT plot_id, smartfarm_valve_name
      FROM ${this.schemas.control}.valve_plot_mapping
      ORDER BY plot_id
    `;
    const result = await db.query(query);
    return result.rows.map((r) => ({ plotId: r.plot_id, valveName: r.smartfarm_valve_name }));
  }
}

module.exports = { TimescaleRepository, moistureColumnForLayer };
