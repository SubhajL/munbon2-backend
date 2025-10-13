const logger = require('../utils/logger');

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
  async getLatestSensorReading(sensorId, sensorType) {
    let tableName;
    let valueColumn;

    if (sensorType === 'moisture') {
      tableName = 'moisture_readings';
      valueColumn = 'moisture_surface_pct';
    } else if (sensorType === 'water-level') {
      tableName = 'water_level_readings';
      valueColumn = 'water_level_cm';
    } else {
      throw new Error(`Unknown sensor type: ${sensorType}`);
    }

    const query = `
      SELECT
        sensor_id,
        ${valueColumn} as value,
        timestamp,
        lat,
        lng
      FROM ${tableName}
      WHERE sensor_id = $1
      ORDER BY timestamp DESC
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

  // Get sensor readings within a time range
  async getSensorHistory(sensorId, sensorType, startDate, endDate) {
    let tableName;
    let valueColumn;

    if (sensorType === 'moisture') {
      tableName = 'moisture_readings';
      valueColumn = 'moisture_surface_pct';
    } else if (sensorType === 'water-level') {
      tableName = 'water_level_readings';
      valueColumn = 'water_level_cm';
    } else {
      throw new Error(`Unknown sensor type: ${sensorType}`);
    }

    const query = `
      SELECT
        sensor_id,
        ${valueColumn} as value,
        timestamp,
        lat,
        lng
      FROM ${tableName}
      WHERE sensor_id = $1
        AND timestamp >= $2
        AND timestamp <= $3
      ORDER BY timestamp ASC
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
      VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
      ON CONFLICT (plot_id, date)
      DO UPDATE SET
        demand_m3 = $3,
        crop_type = $4,
        growth_stage = $5,
        et0 = $6,
        kc = $7,
        effective_rainfall = $8,
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
      WHERE plot_id = $1 AND date = $2
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
      VALUES ($1, $2, $3, $4, $5, CURRENT_TIMESTAMP)
      ON CONFLICT (plot_id, date)
      DO UPDATE SET
        actual_usage = $4,
        efficiency = $5,
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
        water_level_upper_threshold
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
        waterLevelUpperThreshold: parseFloat(row.water_level_upper_threshold)
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

  async close() {
    await this.pool.end();
  }
}

module.exports = { TimescaleRepository };
