const logger = require("../utils/logger");

class WaterBalanceService {
  constructor(config) {
    this.timescalePool = config.timescalePool;
    this.flowRateLPM = config.flowRateLPM || 60; // Default 60 L/min
    this.ongoingCycles = new Map();
  }

  async recordIrrigationCycle(cycle) {
    // Handle ongoing cycles
    if (!cycle.endTime) {
      this.ongoingCycles.set(cycle.plotId, {
        plotId: cycle.plotId,
        startTime: cycle.startTime,
        valveName: cycle.valveName,
        controlMode: cycle.controlMode,
        triggerValue: cycle.triggerValue,
      });
      return;
    }

    // Calculate volume
    const volumeLiters = this.calculateVolumeFromDuration(
      cycle.startTime,
      cycle.endTime,
      cycle.flowRate || this.flowRateLPM,
    );

    try {
      const query = `
        INSERT INTO water_balance_smartfarm
        (plot_id, valve_name, start_time, end_time, volume_liters, control_mode, trigger_value)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
      `;

      await this.timescalePool.query(query, [
        cycle.plotId,
        cycle.valveName,
        cycle.startTime,
        cycle.endTime,
        volumeLiters,
        cycle.controlMode,
        cycle.triggerValue || 0,
      ]);

      logger.info(
        {
          plotId: cycle.plotId,
          volumeLiters,
          duration: (cycle.endTime - cycle.startTime) / 1000 / 60,
        },
        "Irrigation cycle recorded",
      );
    } catch (error) {
      logger.error({ error, cycle }, "Failed to record irrigation cycle");
      throw error;
    }
  }

  startIrrigation(plotId, valveName, controlMode, triggerValue) {
    if (this.ongoingCycles.has(plotId)) {
      logger.warn({ plotId }, "Irrigation already in progress");
      return;
    }

    const cycle = {
      plotId,
      startTime: new Date(),
      valveName,
      controlMode,
      triggerValue,
    };

    this.ongoingCycles.set(plotId, cycle);

    logger.info({ plotId, controlMode, triggerValue }, "Irrigation started");
  }

  async stopIrrigation(plotId, endTime = new Date()) {
    const ongoingCycle = this.ongoingCycles.get(plotId);
    if (!ongoingCycle) {
      logger.warn({ plotId }, "No ongoing irrigation to stop");
      return;
    }

    const completedCycle = {
      ...ongoingCycle,
      endTime,
    };

    await this.recordIrrigationCycle(completedCycle);
    this.ongoingCycles.delete(plotId);

    logger.info(
      { plotId, duration: (endTime - ongoingCycle.startTime) / 1000 / 60 },
      "Irrigation stopped",
    );
  }

  async calculateDailyBalance(plotId, date) {
    try {
      const startOfDay = new Date(date);
      startOfDay.setHours(0, 0, 0, 0);

      const endOfDay = new Date(date);
      endOfDay.setHours(23, 59, 59, 999);

      const query = `
        SELECT
          COALESCE(SUM(volume_liters), 0) as total_usage_liters,
          COALESCE(COUNT(*), 0) as number_of_cycles,
          COALESCE(AVG(EXTRACT(EPOCH FROM (end_time - start_time)) / 60), 0) as average_duration_minutes
        FROM water_balance_smartfarm
        WHERE plot_id = $1
          AND start_time >= $2
          AND start_time <= $3
      `;

      const result = await this.timescalePool.query(query, [
        plotId,
        startOfDay,
        endOfDay,
      ]);

      const row = result.rows[0] || {
        total_usage_liters: 0,
        number_of_cycles: 0,
        average_duration_minutes: 0,
      };

      return {
        plotId,
        date,
        totalUsageLiters: parseInt(row.total_usage_liters),
        numberOfCycles: parseInt(row.number_of_cycles),
        averageCycleDurationMinutes: parseFloat(
          row.average_duration_minutes || 0,
        ),
        efficiency: 0, // Will be calculated separately
      };
    } catch (error) {
      logger.error(
        { error, plotId, date },
        "Failed to calculate daily balance",
      );
      throw error;
    }
  }

  calculateVolumeFromDuration(startTime, endTime, flowRateLPM = null) {
    const durationMinutes = (endTime - startTime) / (1000 * 60);
    const flowRate = flowRateLPM || this.flowRateLPM;
    return Math.round(durationMinutes * flowRate);
  }

  async aggregateUsageMetrics(startDate, endDate) {
    try {
      const query = `
        SELECT
          plot_id,
          SUM(volume_liters) as total_volume,
          COUNT(*) as total_cycles,
          AVG(EXTRACT(EPOCH FROM (end_time - start_time)) / 60) as avg_cycle_duration
        FROM water_balance_smartfarm
        WHERE start_time >= $1 AND start_time <= $2
        GROUP BY plot_id
        ORDER BY plot_id
      `;

      const result = await this.timescalePool.query(query, [
        startDate,
        endDate,
      ]);

      return result.rows.map((row) => ({
        plotId: row.plot_id,
        totalVolumeLiters: parseInt(row.total_volume),
        totalCycles: parseInt(row.total_cycles),
        avgCycleDurationMinutes: parseFloat(row.avg_cycle_duration),
      }));
    } catch (error) {
      logger.error(
        { error, startDate, endDate },
        "Failed to aggregate usage metrics",
      );
      throw error;
    }
  }

  async getEfficiency(plotId, date) {
    try {
      // Get actual usage
      const balance = await this.calculateDailyBalance(plotId, date);

      // Get planned demand
      const demandQuery = `
        SELECT demand_m3
        FROM ros_gis_smartfarm.daily_water_demands
        WHERE plot_id = $1 AND date = $2
      `;

      const demandResult = await this.timescalePool.query(demandQuery, [
        plotId,
        date,
      ]);

      if (demandResult.rows.length === 0) {
        return 0;
      }

      const plannedDemandLiters = demandResult.rows[0].demand_m3 * 1000;

      if (plannedDemandLiters === 0) {
        return 0;
      }

      return (
        Math.round((balance.totalUsageLiters / plannedDemandLiters) * 100) / 100
      );
    } catch (error) {
      logger.error({ error, plotId, date }, "Failed to calculate efficiency");
      return 0;
    }
  }
}

module.exports = { WaterBalanceService };
