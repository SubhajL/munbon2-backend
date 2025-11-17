const logger = require('../utils/logger');

/**
 * Service for logging valve control changes to audit table
 * Records comprehensive context including sensor values, thresholds, and decision reasoning
 */
class ValveAuditService {
  constructor(pool, schema = 'water_control_smartfarm') {
    if (!/^[a-z_][a-z0-9_]*$/i.test(schema)) {
      throw new Error(
        `Invalid schema name: "${schema}". Must contain only letters, numbers, and underscores.`
      );
    }
    this.pool = pool;
    this.schema = schema;
  }

  /**
   * Log a valve control change with full context
   * @param {Object} auditData - Complete audit information
   * @returns {Promise<number>} - ID of created audit record
   */
  async logValveChange(auditData) {
    const requiredFields = [
      'plotId',
      'valveName',
      'newState',
      'controlMode',
      'action',
      'reason'
    ];

    for (const field of requiredFields) {
      if (!auditData[field]) {
        throw new Error(`Missing required field: ${field}`);
      }
    }

    const query = `
      INSERT INTO ${this.schema}.valve_control_audit
        (plot_id, valve_name, changed_at,
         previous_state, new_state,
         moisture_value, water_level_value, sensor_id, sensor_timestamp,
         control_mode,
         moisture_lower_threshold, moisture_upper_threshold,
         water_level_lower_threshold, water_level_upper_threshold,
         action, reason,
         valve_command_sent, valve_command_succeeded, valve_command_error,
         mssql_table_used,
         estimated_duration_minutes, estimated_volume_liters,
         triggered_by, user_id, notes)
      VALUES
        ($1, $2, $3,
         $4, $5,
         $6, $7, $8, $9,
         $10,
         $11, $12, $13, $14,
         $15, $16,
         $17, $18, $19,
         $20,
         $21, $22,
         $23, $24, $25)
      RETURNING id
    `;

    try {
      const moistureValue =
        auditData.moistureValue !== undefined ? auditData.moistureValue : null;
      const waterLevelValue =
        auditData.waterLevelValue !== undefined
          ? auditData.waterLevelValue
          : null;

      const result = await this.pool.query(query, [
        auditData.plotId,
        auditData.valveName,
        auditData.changedAt || new Date(),
        auditData.previousState || 'UNKNOWN',
        auditData.newState,
        moistureValue,
        waterLevelValue,
        auditData.sensorId || null,
        auditData.sensorTimestamp || null,
        auditData.controlMode,
        auditData.moistureLowerThreshold || null,
        auditData.moistureUpperThreshold || null,
        auditData.waterLevelLowerThreshold || null,
        auditData.waterLevelUpperThreshold || null,
        auditData.action,
        auditData.reason,
        auditData.valveCommandSent || false,
        auditData.valveCommandSucceeded || null,
        auditData.valveCommandError || null,
        auditData.mssqlTableUsed || null,
        auditData.estimatedDurationMinutes || null,
        auditData.estimatedVolumeLiters || null,
        auditData.triggeredBy || 'AUTO',
        auditData.userId || null,
        auditData.notes || null
      ]);

      if (result.rows.length === 0) {
        throw new Error('Failed to insert audit record: no rows returned');
      }

      const auditId = Number(result.rows[0].id);

      logger.info(
        {
          auditId,
          plotId: auditData.plotId,
          valveName: auditData.valveName,
          previousState: auditData.previousState,
          newState: auditData.newState,
          action: auditData.action,
          reason: auditData.reason
        },
        'Valve change logged to audit table'
      );

      return auditId;
    } catch (error) {
      logger.error({ error, auditData }, 'Failed to log valve change to audit');
      throw error;
    }
  }

  /**
   * Update audit record with valve command execution result
   * @param {number} auditId - Audit record ID
   * @param {boolean} succeeded - Whether command succeeded
   * @param {string|null} errorMessage - Error message if failed
   */
  async updateCommandResult(auditId, succeeded, errorMessage = null) {
    const query = `
      UPDATE ${this.schema}.valve_control_audit
      SET
        valve_command_succeeded = $2,
        valve_command_error = $3
      WHERE id = $1
    `;

    try {
      await this.pool.query(query, [auditId, succeeded, errorMessage]);

      logger.debug(
        { auditId, succeeded, errorMessage },
        'Audit record updated with command result'
      );
    } catch (error) {
      logger.error(
        { error, auditId, succeeded, errorMessage },
        'Failed to update audit record'
      );
      throw error;
    }
  }

  /**
   * Get audit history for a plot
   * @param {string} plotId - Plot ID
   * @param {Object} options - Query options
   * @returns {Promise<Array>} - Audit records
   */
  async getPlotAuditHistory(plotId, options = {}) {
    const {
      limit = 100,
      offset = 0,
      startDate = null,
      endDate = null
    } = options;

    let query = `
      SELECT
        id, plot_id, valve_name, changed_at,
        previous_state, new_state,
        moisture_value, water_level_value, sensor_id, sensor_timestamp,
        control_mode,
        moisture_lower_threshold, moisture_upper_threshold,
        water_level_lower_threshold, water_level_upper_threshold,
        action, reason,
        valve_command_sent, valve_command_succeeded, valve_command_error,
        mssql_table_used,
        estimated_duration_minutes, estimated_volume_liters,
        triggered_by, user_id, notes,
        created_at
      FROM ${this.schema}.valve_control_audit
      WHERE plot_id = $1
    `;

    const params = [plotId];
    let paramIndex = 2;

    if (startDate) {
      query += ` AND changed_at >= $${paramIndex}`;
      params.push(startDate);
      paramIndex++;
    }

    if (endDate) {
      query += ` AND changed_at <= $${paramIndex}`;
      params.push(endDate);
      paramIndex++;
    }

    query += ` ORDER BY changed_at DESC LIMIT $${paramIndex} OFFSET $${paramIndex + 1}`;
    params.push(limit, offset);

    try {
      const result = await this.pool.query(query, params);
      return result.rows.map((row) => this.mapRowToAuditRecord(row));
    } catch (error) {
      logger.error({ error, plotId, options }, 'Failed to get audit history');
      throw error;
    }
  }

  /**
   * Get recent valve changes across all plots
   * @param {number} limit - Number of records to return
   * @returns {Promise<Array>} - Recent audit records
   */
  async getRecentChanges(limit = 50) {
    const query = `
      SELECT
        id, plot_id, valve_name, changed_at,
        previous_state, new_state,
        moisture_value, water_level_value, sensor_id, sensor_timestamp,
        control_mode,
        moisture_lower_threshold, moisture_upper_threshold,
        water_level_lower_threshold, water_level_upper_threshold,
        action, reason,
        valve_command_sent, valve_command_succeeded, valve_command_error,
        mssql_table_used,
        estimated_duration_minutes, estimated_volume_liters,
        triggered_by, user_id, notes,
        created_at
      FROM ${this.schema}.valve_control_audit
      ORDER BY changed_at DESC
      LIMIT $1
    `;

    try {
      const result = await this.pool.query(query, [limit]);
      return result.rows.map((row) => this.mapRowToAuditRecord(row));
    } catch (error) {
      logger.error({ error, limit }, 'Failed to get recent changes');
      throw error;
    }
  }

  /**
   * Get valve state change statistics
   * @param {string} plotId - Plot ID (optional)
   * @param {Date} startDate - Start date
   * @param {Date} endDate - End date
   * @returns {Promise<Object>} - Statistics
   */
  async getChangeStatistics(plotId = null, startDate, endDate) {
    let query = `
      SELECT
        COUNT(*) as total_changes,
        SUM(CASE WHEN new_state = 'ON' THEN 1 ELSE 0 END) as turn_on_count,
        SUM(CASE WHEN new_state = 'OFF' THEN 1 ELSE 0 END) as turn_off_count,
        SUM(CASE WHEN valve_command_succeeded = true THEN 1 ELSE 0 END) as successful_commands,
        SUM(CASE WHEN valve_command_succeeded = false THEN 1 ELSE 0 END) as failed_commands,
        SUM(estimated_volume_liters) as total_water_used,
        AVG(estimated_duration_minutes) as avg_duration_minutes
      FROM ${this.schema}.valve_control_audit
      WHERE changed_at >= $1 AND changed_at <= $2
    `;

    const params = [startDate, endDate];

    if (plotId) {
      query += ' AND plot_id = $3';
      params.push(plotId);
    }

    try {
      const result = await this.pool.query(query, params);
      const row = result.rows[0];

      return {
        totalChanges: Number(row.total_changes) || 0,
        turnOnCount: Number(row.turn_on_count) || 0,
        turnOffCount: Number(row.turn_off_count) || 0,
        successfulCommands: Number(row.successful_commands) || 0,
        failedCommands: Number(row.failed_commands) || 0,
        totalWaterUsedLiters: Number(row.total_water_used) || 0,
        avgDurationMinutes: row.avg_duration_minutes
          ? Number(row.avg_duration_minutes)
          : 0
      };
    } catch (error) {
      logger.error(
        { error, plotId, startDate, endDate },
        'Failed to get change statistics'
      );
      throw error;
    }
  }

  /**
   * Map database row to audit record object
   * @private
   */
  mapRowToAuditRecord(row) {
    return {
      id: Number(row.id),
      plotId: row.plot_id,
      valveName: row.valve_name,
      changedAt: row.changed_at,
      previousState: row.previous_state,
      newState: row.new_state,
      moistureValue: row.moisture_value ? Number(row.moisture_value) : null,
      waterLevelValue: row.water_level_value
        ? Number(row.water_level_value)
        : null,
      sensorId: row.sensor_id,
      sensorTimestamp: row.sensor_timestamp,
      controlMode: row.control_mode,
      moistureLowerThreshold: row.moisture_lower_threshold
        ? Number(row.moisture_lower_threshold)
        : null,
      moistureUpperThreshold: row.moisture_upper_threshold
        ? Number(row.moisture_upper_threshold)
        : null,
      waterLevelLowerThreshold: row.water_level_lower_threshold
        ? Number(row.water_level_lower_threshold)
        : null,
      waterLevelUpperThreshold: row.water_level_upper_threshold
        ? Number(row.water_level_upper_threshold)
        : null,
      action: row.action,
      reason: row.reason,
      valveCommandSent: row.valve_command_sent,
      valveCommandSucceeded: row.valve_command_succeeded,
      valveCommandError: row.valve_command_error,
      mssqlTableUsed: row.mssql_table_used,
      estimatedDurationMinutes: row.estimated_duration_minutes
        ? Number(row.estimated_duration_minutes)
        : null,
      estimatedVolumeLiters: row.estimated_volume_liters
        ? Number(row.estimated_volume_liters)
        : null,
      triggeredBy: row.triggered_by,
      userId: row.user_id,
      notes: row.notes,
      createdAt: row.created_at
    };
  }
}

module.exports = { ValveAuditService };
