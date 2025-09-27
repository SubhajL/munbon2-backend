const axios = require("axios");
const logger = require("../utils/logger");

class WaterPlanningService {
  constructor(config) {
    this.timescalePool = config.timescalePool;
    this.rosApiUrl = config.rosApiUrl;
    this.rosApiKey = config.rosApiKey;
    this.plotConfigs = config.plotConfigs;
    this.demandCache = new Map();
  }

  async calculateDailyDemand(plotId, date) {
    const cacheKey = `${plotId}-${date.toISOString().split("T")[0]}`;

    // Check cache first
    if (this.demandCache.has(cacheKey)) {
      logger.info({ plotId, date }, "Returning cached water demand");
      return this.demandCache.get(cacheKey);
    }

    const plotConfig = this.plotConfigs.find((p) => p.plotId === plotId);
    if (!plotConfig) {
      throw new Error(`Plot configuration not found: ${plotId}`);
    }

    try {
      const rosInput = this.prepareROSInput(plotConfig, date);

      // Use configured endpoint or default to new ROS API structure
      const endpoint = process.env.ROS_CALCULATION_ENDPOINT || '/api/v1/ros/demand/calculate';
      const fullUrl = endpoint.startsWith('http') ? endpoint : `${this.rosApiUrl}${endpoint}`;

      const response = await axios.post(
        fullUrl,
        rosInput,
        {
          headers: {
            "X-API-Key": this.rosApiKey,
            "Content-Type": "application/json",
          },
          timeout: 30000, // 30 second timeout for ROS calculations
        },
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
        effectiveRainfall: rosOutput.effectiveRainfall.amount_m3,
      };

      // Cache the result
      this.demandCache.set(cacheKey, demand);

      logger.info(
        {
          plotId,
          date,
          demandCubicMeters: demand.demandCubicMeters,
        },
        "Water demand calculated",
      );

      return demand;
    } catch (error) {
      logger.error({ error, plotId, date }, "Failed to calculate water demand");
      throw error;
    }
  }

  async syncToTimescale(demands) {
    for (const demand of demands) {
      try {
        const query = `
          INSERT INTO ros_gis_smartfarm.daily_water_demands
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

        await this.timescalePool.query(query, [
          demand.plotId,
          demand.date,
          demand.demandCubicMeters,
          demand.cropType,
          demand.growthStage,
          demand.et0,
          demand.kc,
          demand.effectiveRainfall,
        ]);

        logger.info(
          { plotId: demand.plotId, date: demand.date },
          "Water demand synced to TimescaleDB",
        );
      } catch (error) {
        logger.error({ error, demand }, "Failed to sync water demand");
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

      const query = `
        INSERT INTO ros_gis_smartfarm.daily_progress
        (plot_id, date, planned_demand, actual_usage, efficiency, last_updated)
        VALUES ($1, $2, $3, $4, $5, CURRENT_TIMESTAMP)
        ON CONFLICT (plot_id, date)
        DO UPDATE SET
          actual_usage = $4,
          efficiency = $5,
          last_updated = CURRENT_TIMESTAMP
      `;

      await this.timescalePool.query(query, [
        plotId,
        date,
        plannedDemand,
        actualUsage,
        efficiency,
      ]);

      logger.info(
        {
          plotId,
          date,
          plannedDemand,
          actualUsage,
          efficiency,
        },
        "Daily progress updated",
      );
    } catch (error) {
      logger.error({ error, plotId, date }, "Failed to update daily progress");
      throw error;
    }
  }

  async getPlannedDemand(plotId, date) {
    try {
      const query = `
        SELECT demand_m3
        FROM ros_gis_smartfarm.daily_water_demands
        WHERE plot_id = $1 AND date = $2
      `;

      const result = await this.timescalePool.query(query, [plotId, date]);

      return result.rows.length > 0 ? result.rows[0].demand_m3 : 0;
    } catch (error) {
      logger.error({ error, plotId, date }, "Failed to get planned demand");
      return 0;
    }
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
          "Failed to calculate demand for plot",
        );
      }
    }

    return demands;
  }

  prepareROSInput(plotConfig, date) {
    return {
      cropType: plotConfig.cropType,
      calculationDate: date.toISOString().split("T")[0],
      calculationPeriod: 1, // Daily calculation
      plantings: [
        {
          plantingDate: this.getPlantingDate(plotConfig, date),
          areaRai: plotConfig.areaRai,
          growthDays: null, // Let ROS calculate based on planting date
        },
      ],
      nonAgriculturalDemands: [],
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
    if (kc < 0.6) return "initial";
    if (kc < 1.0) return "development";
    if (kc < 1.2) return "mid-season";
    return "late-season";
  }
}

module.exports = { WaterPlanningService };
