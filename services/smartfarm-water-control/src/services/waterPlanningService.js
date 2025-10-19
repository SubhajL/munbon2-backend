const axios = require('axios');
const logger = require('../utils/logger');

class WaterPlanningService {
  constructor(config) {
    this.timescaleRepository = config.timescaleRepository;
    this.waterPlanningUrl = config.waterPlanningUrl;
    this.waterPlanningApiKey = config.waterPlanningApiKey;
    this.waterPlanningEndpoint = config.waterPlanningEndpoint || '/api/v1/water-demand/calculate';
    this.timeout = config.timeout || 10000;
    this.plotConfigs = config.plotConfigs;
    this.demandCache = new Map();
  }

  async calculateDailyDemand(plotId, date) {
    const cacheKey = `${plotId}-${date.toISOString().split('T')[0]}`;

    // Check cache first
    if (this.demandCache.has(cacheKey)) {
      logger.info({ plotId, date }, 'Returning cached water demand');
      return this.demandCache.get(cacheKey);
    }

    const plotConfig = this.plotConfigs.find((p) => p.plotId === plotId);
    if (!plotConfig) {
      throw new Error(`Plot configuration not found: ${plotId}`);
    }

    try {
      const demandInput = this.prepareDemandInput(plotConfig, date);

      const fullUrl = this.waterPlanningEndpoint.startsWith('http')
        ? this.waterPlanningEndpoint
        : `${this.waterPlanningUrl}${this.waterPlanningEndpoint}`;

      const response = await axios.post(
        fullUrl,
        demandInput,
        {
          headers: {
            'X-API-Key': this.waterPlanningApiKey,
            'Content-Type': 'application/json'
          },
          timeout: this.timeout
        }
      );

      const demandOutput = response.data;

      const demand = {
        plotId,
        date,
        demandCubicMeters: demandOutput.combined_demand_m3 || demandOutput.awd_demand_m3 || 0,
        cropType: plotConfig.cropType,
        growthStage: 'mid-season', // Simplified for now
        et0: demandOutput.et0_mm || 4.5,
        kc: demandOutput.avg_kc_factor || 1.1,
        effectiveRainfall: demandOutput.effective_rainfall_m3 || 0
      };

      // Cache the result
      this.demandCache.set(cacheKey, demand);

      logger.info(
        {
          plotId,
          date,
          demandCubicMeters: demand.demandCubicMeters
        },
        'Water demand calculated'
      );

      return demand;
    } catch (error) {
      logger.error({ error, plotId, date }, 'Failed to calculate water demand');
      throw error;
    }
  }

  async syncToTimescale(demands) {
    for (const demand of demands) {
      try {
        await this.timescaleRepository.saveWaterDemand(demand);

        logger.info(
          { plotId: demand.plotId, date: demand.date },
          'Water demand synced to TimescaleDB'
        );
      } catch (error) {
        logger.error({ error, demand }, 'Failed to sync water demand');
        throw error;
      }
    }
  }

  async updateDailyProgress(plotId, actualUsage, date) {
    try {
      // Get planned demand
      const plannedDemand = await this.getPlannedDemand(plotId, date);

      const efficiency =
        plannedDemand > 0
          ? Math.round((actualUsage / plannedDemand) * 100) / 100
          : 0;

      await this.timescaleRepository.saveDailyProgress(
        plotId,
        date,
        plannedDemand,
        actualUsage,
        efficiency
      );

      logger.info(
        {
          plotId,
          date,
          plannedDemand,
          actualUsage,
          efficiency
        },
        'Daily progress updated'
      );
    } catch (error) {
      logger.error({ error, plotId, date }, 'Failed to update daily progress');
      throw error;
    }
  }

  async getPlannedDemand(plotId, date) {
    return await this.timescaleRepository.getPlannedDemand(plotId, date);
  }

  async calculateAllPlotsDemand(date) {
    const demands = [];

    for (const plotConfig of this.plotConfigs) {
      try {
        const demand = await this.calculateDailyDemand(plotConfig.plotId, date);
        demands.push(demand);
      } catch (error) {
        logger.error(
          { error, plotId: plotConfig.plotId },
          'Failed to calculate demand for plot'
        );
      }
    }

    return demands;
  }

  prepareDemandInput(plotConfig, date) {
    return {
      plot_id: plotConfig.plotId,
      date: date.toISOString().split('T')[0],
      crop_type: plotConfig.cropType || 'rice',
      area_rai: plotConfig.areaRai || 1.0,
      control_mode: plotConfig.controlMode || 'MOISTURE',
      planting_date: this.getPlantingDate(plotConfig, date).toISOString().split('T')[0],
      calculation_method: 'combined' // Use combined ROS + RID-MS calculation
    };
  }

  getPlantingDate(plotConfig, currentDate) {
    // Default: assume planted 30 days ago
    // In production, this would come from a planting schedule database
    const plantingDate = new Date(currentDate);
    plantingDate.setDate(plantingDate.getDate() - 30);
    return plantingDate;
  }

  determineGrowthStage(cropDetails) {
    if (
      cropDetails.activeGrowthStages &&
      cropDetails.activeGrowthStages.length > 0
    ) {
      return cropDetails.activeGrowthStages[0].growthStage;
    }

    // Fallback based on Kc value
    const kc = cropDetails.weightedKc;
    if (kc < 0.6) return 'initial';
    if (kc < 1.0) return 'development';
    if (kc < 1.2) return 'mid-season';
    return 'late-season';
  }
}

module.exports = { WaterPlanningService };
