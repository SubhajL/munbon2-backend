const logger = require('../utils/logger');

class WaterBalanceService {
  constructor(config) {
    this.timescaleRepository = config.timescaleRepository;
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
        triggerValue: cycle.triggerValue
      });
      return;
    }

    // Calculate volume
    const volumeLiters = this.calculateVolumeFromDuration(
      cycle.startTime,
      cycle.endTime,
      cycle.flowRate || this.flowRateLPM
    );

    try {
      await this.timescaleRepository.recordIrrigationCycle({
        ...cycle,
        volumeLiters
      });

      logger.info(
        {
          plotId: cycle.plotId,
          volumeLiters,
          duration: (cycle.endTime - cycle.startTime) / 1000 / 60
        },
        'Irrigation cycle recorded'
      );
    } catch (error) {
      logger.error({ error, cycle }, 'Failed to record irrigation cycle');
      throw error;
    }
  }

  startIrrigation(plotId, valveName, controlMode, triggerValue) {
    if (this.ongoingCycles.has(plotId)) {
      logger.warn({ plotId }, 'Irrigation already in progress');
      return;
    }

    const cycle = {
      plotId,
      startTime: new Date(),
      valveName,
      controlMode,
      triggerValue
    };

    this.ongoingCycles.set(plotId, cycle);

    logger.info({ plotId, controlMode, triggerValue }, 'Irrigation started');
  }

  async stopIrrigation(plotId, endTime = new Date()) {
    const ongoingCycle = this.ongoingCycles.get(plotId);
    if (!ongoingCycle) {
      logger.warn({ plotId }, 'No ongoing irrigation to stop');
      return;
    }

    const completedCycle = {
      ...ongoingCycle,
      endTime
    };

    await this.recordIrrigationCycle(completedCycle);
    this.ongoingCycles.delete(plotId);

    logger.info(
      { plotId, duration: (endTime - ongoingCycle.startTime) / 1000 / 60 },
      'Irrigation stopped'
    );
  }

  async calculateDailyBalance(plotId, date) {
    try {
      const startOfDay = new Date(date);
      startOfDay.setHours(0, 0, 0, 0);

      const endOfDay = new Date(date);
      endOfDay.setHours(23, 59, 59, 999);

      const balance = await this.timescaleRepository.getDailyWaterBalance(
        plotId,
        startOfDay,
        endOfDay
      );

      return {
        plotId,
        date,
        totalUsageLiters: parseInt(balance.total_usage_liters),
        numberOfCycles: parseInt(balance.number_of_cycles),
        averageCycleDurationMinutes: parseFloat(
          balance.average_duration_minutes || 0
        ),
        efficiency: 0 // Will be calculated separately
      };
    } catch (error) {
      logger.error(
        { error, plotId, date },
        'Failed to calculate daily balance'
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
      return await this.timescaleRepository.getAggregatedUsageMetrics(
        startDate,
        endDate
      );
    } catch (error) {
      logger.error(
        { error, startDate, endDate },
        'Failed to aggregate usage metrics'
      );
      throw error;
    }
  }

  async getEfficiency(plotId, date) {
    try {
      // Get actual usage
      const balance = await this.calculateDailyBalance(plotId, date);

      // Get planned demand
      const plannedDemandM3 = await this.timescaleRepository.getPlannedDemand(
        plotId,
        date
      );

      if (plannedDemandM3 === 0) {
        return 0;
      }

      const plannedDemandLiters = plannedDemandM3 * 1000;

      return (
        Math.round((balance.totalUsageLiters / plannedDemandLiters) * 100) / 100
      );
    } catch (error) {
      logger.error({ error, plotId, date }, 'Failed to calculate efficiency');
      return 0;
    }
  }
}

module.exports = { WaterBalanceService };
