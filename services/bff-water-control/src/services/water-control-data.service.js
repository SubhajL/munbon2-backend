const { Client } = require('pg');
const { startOfWeek, endOfWeek, format } = require('date-fns');
const logger = require('../utils/logger');

class WaterControlDataService {
  constructor() {
    this.client = null;
    this.pgConfig = {
      host: process.env.PG_HOST || '43.208.201.191',
      port: process.env.PG_PORT || 5432,
      database: process.env.PG_DATABASE || 'munbon_dev',
      user: process.env.PG_USER || 'postgres',
      password: process.env.PG_PASSWORD || (() => { throw new Error('PG_PASSWORD env var is required (hardcoded default removed; SEC remediation)'); })()
    };
  }

  async ensureConnection() {
    if (!this.client || !this.client._connected) {
      this.client = new Client(this.pgConfig);
      await this.client.connect();
    }
    return this.client;
  }

  /**
   * Get weekly water control schedule for a zone
   * This is the main method for the mobile app display
   */
  async getWeeklySchedule(zoneId, options = {}) {
    try {
      const client = await this.ensureConnection();
      
      // Determine week range
      const weekStart = options.weekStart 
        ? new Date(options.weekStart) 
        : startOfWeek(new Date(), { weekStartsOn: 1 });
      const weekEnd = options.weekEnd 
        ? new Date(options.weekEnd)
        : endOfWeek(weekStart, { weekStartsOn: 1 });

      // Get weekly control data
      const controlQuery = `
        SELECT 
          wc.id,
          wc.week_start_date,
          wc.zone_id,
          wc.section_id,
          wc.total_demand_m3,
          wc.total_flow_m3s,
          wc.priority_level,
          wc.algorithm_type,
          wc.optimization_score,
          wc.automatic_gates_count,
          wc.manual_gates_count,
          wc.total_operations,
          wc.status,
          wc.scheduled_start,
          wc.actual_start,
          wc.actual_end,
          wc.notes
        FROM water_control.weekly_water_controls wc
        WHERE wc.zone_id = $1
          AND wc.week_start_date = $2
        ORDER BY wc.priority_level DESC, wc.section_id
      `;

      const controlResult = await client.query(controlQuery, [zoneId, weekStart]);

      if (controlResult.rows.length === 0) {
        return null;
      }

      const weeklyControl = controlResult.rows[0];

      // Get detailed progress for all controls in this week
      const progressQuery = `
        SELECT 
          p.id,
          p.weekly_control_id,
          p.week_start_date,
          p.operation_sequence,
          p.gate_id,
          p.gate_type,
          p.gate_location,
          p.gate_level,
          p.cumulative_opening_cm,
          p.opening_height_cm,
          p.open_time,
          p.close_time,
          p.operation_duration_hours,
          p.target_flow_m3s,
          p.expected_volume_m3,
          p.scheduled_datetime,
          p.actual_start_datetime,
          p.actual_end_datetime,
          p.execution_status,
          p.actual_flow_m3s,
          p.actual_volume_m3,
          p.flow_accuracy_pct,
          p.job_order_id,
          p.operator_name,
          p.operator_team,
          p.instructions,
          p.sensor_readings,
          p.adjustments_made,
          p.alerts_triggered,
          p.execution_notes
        FROM water_control.crop_season_weekly_progress p
        WHERE p.weekly_control_id = $1
        ORDER BY p.scheduled_datetime, p.operation_sequence
      `;

      const progressResult = await client.query(progressQuery, [weeklyControl.id]);

      // Group progress by gate type
      const automaticGates = [];
      const manualGates = [];

      progressResult.rows.forEach(progress => {
        const gateData = {
          id: progress.id,
          gate_id: progress.gate_id,
          gate_location: progress.gate_location,
          scheduled_datetime: progress.scheduled_datetime,
          execution_status: progress.execution_status,
          target_flow_m3s: parseFloat(progress.target_flow_m3s),
          expected_volume_m3: parseFloat(progress.expected_volume_m3)
        };

        if (progress.gate_type === 'automatic') {
          automaticGates.push({
            ...gateData,
            gate_level: progress.gate_level,
            cumulative_opening_cm: parseFloat(progress.cumulative_opening_cm),
            actual_flow_m3s: progress.actual_flow_m3s ? parseFloat(progress.actual_flow_m3s) : null,
            flow_accuracy_pct: progress.flow_accuracy_pct ? parseFloat(progress.flow_accuracy_pct) : null
          });
        } else {
          manualGates.push({
            ...gateData,
            opening_height_cm: parseFloat(progress.opening_height_cm),
            open_time: progress.open_time,
            close_time: progress.close_time,
            operation_duration_hours: parseFloat(progress.operation_duration_hours),
            job_order_id: progress.job_order_id,
            operator_name: progress.operator_name,
            operator_team: progress.operator_team,
            instructions: progress.instructions
          });
        }
      });

      // Get monitoring summary if available
      const monitoringQuery = `
        SELECT 
          total_planned_operations,
          completed_operations,
          failed_operations,
          total_planned_volume_m3,
          total_delivered_volume_m3,
          delivery_efficiency_pct,
          total_alerts,
          critical_alerts,
          unresolved_issues
        FROM water_control.weekly_control_monitoring
        WHERE weekly_control_id = $1
        ORDER BY monitoring_date DESC
        LIMIT 1
      `;

      const monitoringResult = await client.query(monitoringQuery, [weeklyControl.id]);
      const monitoring = monitoringResult.rows[0] || null;

      return {
        weekly_control: {
          id: weeklyControl.id,
          week_start_date: weeklyControl.week_start_date,
          zone_id: weeklyControl.zone_id,
          section_id: weeklyControl.section_id,
          total_demand_m3: parseFloat(weeklyControl.total_demand_m3),
          total_flow_m3s: parseFloat(weeklyControl.total_flow_m3s),
          priority_level: weeklyControl.priority_level,
          algorithm_type: weeklyControl.algorithm_type,
          status: weeklyControl.status,
          scheduled_start: weeklyControl.scheduled_start,
          actual_start: weeklyControl.actual_start,
          actual_end: weeklyControl.actual_end
        },
        automatic_gates: automaticGates,
        manual_gates: manualGates,
        summary: {
          total_automatic_gates: automaticGates.length,
          total_manual_gates: manualGates.length,
          total_operations: automaticGates.length + manualGates.length,
          pending_operations: [...automaticGates, ...manualGates].filter(g => g.execution_status === 'pending').length,
          completed_operations: [...automaticGates, ...manualGates].filter(g => g.execution_status === 'completed').length,
          failed_operations: [...automaticGates, ...manualGates].filter(g => g.execution_status === 'failed').length
        },
        monitoring: monitoring ? {
          delivery_efficiency_pct: parseFloat(monitoring.delivery_efficiency_pct),
          total_alerts: monitoring.total_alerts,
          critical_alerts: monitoring.critical_alerts,
          unresolved_issues: monitoring.unresolved_issues
        } : null
      };

    } catch (error) {
      logger.error('Error getting weekly schedule:', error);
      throw error;
    }
  }

  /**
   * Get current week schedule for a zone
   */
  async getCurrentWeekSchedule(zoneId) {
    const currentWeekStart = startOfWeek(new Date(), { weekStartsOn: 1 });
    return this.getWeeklySchedule(zoneId, { weekStart: currentWeekStart });
  }

  /**
   * Get schedule for a specific gate
   */
  async getGateSchedule(gateId, options = {}) {
    try {
      const client = await this.ensureConnection();
      
      let query = `
        SELECT 
          p.*,
          wc.zone_id,
          wc.section_id,
          wc.status as control_status
        FROM water_control.crop_season_weekly_progress p
        JOIN water_control.weekly_water_controls wc ON p.weekly_control_id = wc.id
        WHERE p.gate_id = $1
      `;

      const params = [gateId];
      let paramIndex = 2;

      if (options.weekStart) {
        query += ` AND p.week_start_date >= $${paramIndex}`;
        params.push(new Date(options.weekStart));
        paramIndex++;
      }

      if (options.weekEnd) {
        query += ` AND p.week_start_date <= $${paramIndex}`;
        params.push(new Date(options.weekEnd));
        paramIndex++;
      }

      if (options.status) {
        query += ` AND p.execution_status = $${paramIndex}`;
        params.push(options.status);
        paramIndex++;
      }

      query += ' ORDER BY p.scheduled_datetime DESC';

      const result = await client.query(query, params);

      return result.rows.map(record => ({
        id: record.id,
        week_start_date: record.week_start_date,
        zone_id: record.zone_id,
        section_id: record.section_id,
        gate_type: record.gate_type,
        gate_level: record.gate_level,
        opening_height_cm: record.opening_height_cm,
        open_time: record.open_time,
        close_time: record.close_time,
        scheduled_datetime: record.scheduled_datetime,
        execution_status: record.execution_status,
        actual_flow_m3s: record.actual_flow_m3s,
        flow_accuracy_pct: record.flow_accuracy_pct
      }));

    } catch (error) {
      logger.error('Error getting gate schedule:', error);
      throw error;
    }
  }

  /**
   * Get schedule for a specific section
   */
  async getSectionSchedule(sectionId, options = {}) {
    try {
      const client = await this.ensureConnection();
      
      const weekStart = options.weekStart 
        ? new Date(options.weekStart) 
        : startOfWeek(new Date(), { weekStartsOn: 1 });

      const query = `
        SELECT 
          wc.*,
          (
            SELECT COUNT(*) 
            FROM water_control.crop_season_weekly_progress p 
            WHERE p.weekly_control_id = wc.id
          ) as total_operations
        FROM water_control.weekly_water_controls wc
        WHERE wc.section_id = $1
          AND wc.week_start_date = $2
      `;

      const result = await client.query(query, [sectionId, weekStart]);

      if (result.rows.length === 0) {
        return null;
      }

      const control = result.rows[0];

      // Get gate details if requested
      if (options.includeGateDetails) {
        const progressQuery = `
          SELECT * FROM water_control.crop_season_weekly_progress
          WHERE weekly_control_id = $1
          ORDER BY scheduled_datetime, operation_sequence
        `;

        const progressResult = await client.query(progressQuery, [control.id]);
        control.gate_operations = progressResult.rows;
      }

      return control;

    } catch (error) {
      logger.error('Error getting section schedule:', error);
      throw error;
    }
  }

  /**
   * Get manual gate job orders
   */
  async getManualGateJobOrders(filters = {}) {
    try {
      const client = await this.ensureConnection();
      
      let query = `
        SELECT 
          p.id,
          p.gate_id,
          p.gate_location,
          p.opening_height_cm,
          p.open_time,
          p.close_time,
          p.operation_duration_hours,
          p.scheduled_datetime,
          p.execution_status,
          p.job_order_id,
          p.operator_name,
          p.operator_team,
          p.instructions,
          wc.zone_id,
          wc.section_id
        FROM water_control.crop_season_weekly_progress p
        JOIN water_control.weekly_water_controls wc ON p.weekly_control_id = wc.id
        WHERE p.gate_type = 'manual'
      `;

      const params = [];
      let paramIndex = 1;

      if (filters.zoneId) {
        query += ` AND wc.zone_id = $${paramIndex}`;
        params.push(filters.zoneId);
        paramIndex++;
      }

      if (filters.status) {
        query += ` AND p.execution_status = $${paramIndex}`;
        params.push(filters.status);
        paramIndex++;
      }

      if (filters.dateFrom) {
        query += ` AND p.scheduled_datetime >= $${paramIndex}`;
        params.push(new Date(filters.dateFrom));
        paramIndex++;
      }

      if (filters.dateTo) {
        query += ` AND p.scheduled_datetime <= $${paramIndex}`;
        params.push(new Date(filters.dateTo));
        paramIndex++;
      }

      query += ' ORDER BY p.scheduled_datetime ASC';

      const result = await client.query(query, params);

      return result.rows.map(record => ({
        id: record.id,
        job_order_id: record.job_order_id,
        gate_id: record.gate_id,
        gate_location: record.gate_location,
        zone_id: record.zone_id,
        section_id: record.section_id,
        opening_height_cm: parseFloat(record.opening_height_cm),
        open_time: record.open_time,
        close_time: record.close_time,
        operation_duration_hours: parseFloat(record.operation_duration_hours),
        scheduled_datetime: record.scheduled_datetime,
        execution_status: record.execution_status,
        operator: {
          name: record.operator_name,
          team: record.operator_team
        },
        instructions: record.instructions
      }));

    } catch (error) {
      logger.error('Error getting manual gate job orders:', error);
      throw error;
    }
  }

  /**
   * Update progress status
   */
  async updateProgress(progressId, updateData) {
    try {
      const client = await this.ensureConnection();
      
      const allowedFields = [
        'actual_start_datetime',
        'actual_end_datetime',
        'execution_status',
        'actual_flow_m3s',
        'actual_volume_m3',
        'flow_accuracy_pct',
        'execution_notes'
      ];

      const setClause = [];
      const values = [];
      let paramIndex = 1;

      Object.keys(updateData).forEach(field => {
        if (allowedFields.includes(field)) {
          setClause.push(`${field} = $${paramIndex}`);
          values.push(updateData[field]);
          paramIndex++;
        }
      });

      if (setClause.length === 0) {
        throw new Error('No valid fields to update');
      }

      // Always update the updated_at timestamp
      setClause.push('updated_at = CURRENT_TIMESTAMP');
      values.push(progressId);

      const query = `
        UPDATE water_control.crop_season_weekly_progress
        SET ${setClause.join(', ')}
        WHERE id = $${paramIndex}
        RETURNING *
      `;

      const result = await client.query(query, values);
      
      return result.rows[0];

    } catch (error) {
      logger.error('Error updating progress:', error);
      throw error;
    }
  }

  /**
   * Get weekly monitoring data
   */
  async getWeeklyMonitoring(weeklyControlId, date = null) {
    try {
      const client = await this.ensureConnection();
      
      let query = `
        SELECT * FROM water_control.weekly_control_monitoring
        WHERE weekly_control_id = $1
      `;
      
      const params = [weeklyControlId];

      if (date) {
        query += ' AND monitoring_date = $2';
        params.push(new Date(date));
      }

      query += ' ORDER BY monitoring_date DESC';

      const result = await client.query(query, params);
      
      return date ? result.rows[0] : result.rows;

    } catch (error) {
      logger.error('Error getting weekly monitoring:', error);
      throw error;
    }
  }

  /**
   * Create a new recommendation
   */
  async createRecommendation(data) {
    try {
      const client = await this.ensureConnection();
      
      const query = `
        INSERT INTO water_control.gate_control_recommendations (
          weekly_control_id,
          progress_id,
          recommendation_type,
          severity,
          current_value,
          recommended_value,
          reason
        ) VALUES (
          $1, $2, $3, $4, $5, $6, $7
        )
        RETURNING *
      `;

      const values = [
        data.weekly_control_id,
        data.progress_id || null,
        data.recommendation_type,
        data.severity,
        data.current_value || null,
        data.recommended_value || null,
        data.reason
      ];

      const result = await client.query(query, values);
      return result.rows[0];

    } catch (error) {
      logger.error('Error creating recommendation:', error);
      throw error;
    }
  }

  /**
   * Get status overview for dashboard
   */
  async getStatusOverview(zoneId = null) {
    try {
      const client = await this.ensureConnection();
      
      let query = `
        SELECT 
          wc.zone_id,
          wc.status,
          COUNT(DISTINCT wc.id) as control_count,
          SUM(wc.automatic_gates_count) as total_automatic_gates,
          SUM(wc.manual_gates_count) as total_manual_gates,
          SUM(wc.total_operations) as total_operations,
          AVG(wc.optimization_score) as avg_optimization_score
        FROM water_control.weekly_water_controls wc
        WHERE wc.week_start_date >= CURRENT_DATE - INTERVAL '4 weeks'
      `;

      const params = [];

      if (zoneId) {
        query += ' AND wc.zone_id = $1';
        params.push(zoneId);
      }

      query += ' GROUP BY wc.zone_id, wc.status';

      const result = await client.query(query, params);

      // Get current week active operations
      let activeQuery = `
        SELECT COUNT(*) as active_operations
        FROM water_control.crop_season_weekly_progress p
        JOIN water_control.weekly_water_controls wc ON p.weekly_control_id = wc.id
        WHERE p.execution_status IN ('pending', 'executing')
          AND p.scheduled_datetime >= CURRENT_DATE - INTERVAL '7 days'
      `;

      if (zoneId) {
        activeQuery += ' AND wc.zone_id = $1';
      }

      const activeResult = await client.query(activeQuery, params);

      return {
        zones: result.rows,
        active_operations: parseInt(activeResult.rows[0].active_operations),
        last_updated: new Date()
      };

    } catch (error) {
      logger.error('Error getting status overview:', error);
      throw error;
    }
  }
}

module.exports = new WaterControlDataService();