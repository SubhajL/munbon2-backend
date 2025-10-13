const axios = require('axios');
const logger = require('../utils/logger');

class WaterPlanningService {
  constructor(config) {
    this.timescaleRepository = config.timescaleRepository;
    this.rosApiUrl = config.rosApiUrl;
    this.rosApiKey = config.rosApiKey;
    this.rosEndpoint = config.rosEndpoint || '/api/v1/ros/demand/calculate';
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
      const rosInput = this.prepareROSInput(plotConfig, date);

      const fullUrl = this.rosEndpoint.startsWith('http')
        ? this.rosEndpoint
        : `${this.rosApiUrl}${this.rosEndpoint}`;

      const response = await axios.post(
        fullUrl,
        rosInput,
        {
          headers: {
            'X-API-Key': this.rosApiKey,
            'Content-Type': 'application/json'
          },
          timeout: 30000
        }
      );

      const rosOutput = response.data;

      const demand = {
        plotId,
        date,
        demandCubicMeters: rosOutput.netIrrigation.amount_m3,
        cropType: plotConfig.cropType,
        growthStage: this.determineGrowthStage(rosOutput.cropDetails),
        et0: rosOutput.cropDetails.et0,
        kc: rosOutput.cropDetails.weightedKc,
        effectiveRainfall: rosOutput.effectiveRainfall.amount_m3
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

  prepareROSInput(plotConfig, date) {
    return {
      cropType: plotConfig.cropType,
      calculationDate: date.toISOString().split('T')[0],
      calculationPeriod: 1, // Daily calculation
      plantings: [
        {
          plantingDate: this.getPlantingDate(plotConfig, date),
          areaRai: plotConfig.areaRai,
          growthDays: null // Let ROS calculate based on planting date
        }
      ],
      nonAgriculturalDemands: []
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
