const axios = require('axios');
const logger = require('../utils/logger');
const { tokenizeCropType } = require('../utils/kc-utils');

class WaterPlanningService {
  constructor(config) {
    this.planningRepository = config.planningRepository || config.timescaleRepository;
    this.configRepository = config.configRepository; // read-only access to munbon_dev
    this.waterPlanningUrl = config.waterPlanningUrl;
    this.waterPlanningApiKey = config.waterPlanningApiKey;
    this.waterPlanningEndpoint = config.waterPlanningEndpoint || '/api/v1/water-demand/calculate';
    this.timeout = config.timeout || 10000;
    this.plotConfigs = config.plotConfigs;
    this.mode = config.mode || (this.waterPlanningUrl ? 'external' : 'internal');
    this.demandCache = new Map();
  }

  extractDemandM3(responseData) {
    const path = 'netIrrigation.amount_m3';
    const val = responseData && responseData.netIrrigation && responseData.netIrrigation.amount_m3;
    const num = Number(val);
    if (!Number.isFinite(num)) {
      throw new Error(`Missing or invalid ${path}`);
    }
    return num;
  }

  calculateCropWeek(plantingDate, currentDate) {
    const start = new Date(plantingDate);
    const cur = new Date(currentDate);
    const days = Math.floor((cur.getTime() - start.getTime()) / (1000 * 60 * 60 * 24));
    if (days < 0) return null;
    return Math.floor(days / 7) + 1;
  }

  isValidCropWeek(cropType, cropWeek) {
    const limits = { rice: 16, corn: 14 };
    const max = limits[(cropType || '').toLowerCase()] || 16;
    return cropWeek >= 1 && cropWeek <= max;
  }

  getCalendarWeekYearFromPlanting(plantingDate, cropWeek) {
    const d = new Date(plantingDate);
    d.setDate(d.getDate() + (cropWeek - 1) * 7);
    // ISO week: approximate using getWeek from Monday-based; keep simple here
    const onejan = new Date(d.getFullYear(), 0, 1);
    const days = Math.floor((d - onejan) / 86400000);
    const calendarWeek = Math.floor((days + onejan.getDay() + 6) / 7);
    return { calendarWeek, calendarYear: d.getFullYear() };
  }

  async calculateDailyDemandInternal(plotId, date) {
    const repo = this.planningRepository;
    const cfg = this.plotConfigs.find((p) => p.plotId === plotId) || {};

    // Prefer config repository (munbon_dev) for planting_date and area_rai
    let plantingDate;
    let areaRai;
    try {
      if (this.configRepository) {
        const q1 = `SELECT planting_date FROM ${this.configRepository.schemas.control}.plot_configurations WHERE plot_id = $1`;
        const r1 = await this.configRepository.pool.query(q1, [plotId]);
        if (r1.rows.length && r1.rows[0].planting_date) {
          plantingDate = new Date(r1.rows[0].planting_date);
        }
        const q2 = `SELECT area_rai FROM ${this.configRepository.schemas.control}.v_plot_configurations_enriched WHERE plot_id = $1`;
        const r2 = await this.configRepository.pool.query(q2, [plotId]);
        if (r2.rows.length && r2.rows[0].area_rai != null) {
          areaRai = parseFloat(r2.rows[0].area_rai);
        }
      }
    } catch (e) {
      // ignore and handle below
    }

    // If critical inputs missing, skip this plot
    if (!plantingDate || !Number.isFinite(areaRai)) {
      logger.warn({ plotId }, 'Skipping demand calc: missing planting_date or area_rai');
      return null;
    }

    const cropType = (cfg.cropType || 'rice');

    const cropWeek = this.calculateCropWeek(plantingDate, date);
    if (cropWeek === null) {
      logger.warn({ plotId }, 'Skipping demand calc: date before planting');
      return null;
    }

    const { calendarWeek, calendarYear } = this.getCalendarWeekYearFromPlanting(plantingDate, cropWeek);

    // Try to fetch Kc/ET0/effective rainfall from DB; fallback to defaults if unavailable
    const tryQuery = async (sqls, params) => {
      for (const sql of sqls) {
        try {
          const { rows } = await this.configRepository.pool.query(sql, params);
          if (rows.length) return rows[0];
        } catch (_e) {
          // try next
        }
      }
      return null;
    };

    // Resolve Kc using tokenized cropType and over‑max policy
    let kcResolved = { kc: 1.1, reason: 'default' };
    if (this.configRepository) {
      kcResolved = await this.resolveKcWithTokens(cropType, cropWeek);
    }
    const kc = kcResolved.kc;

    let et0 = 4.5;
    const et0Row = this.configRepository
      ? await tryQuery([
          'SELECT eto_value AS v FROM ros_smartfarm.eto_weekly WHERE aos_station = $1 AND province = $2 AND calendar_week = $3 AND calendar_year = $4'
        ], ['นครราชสีมา', 'นครราชสีมา', calendarWeek, calendarYear])
      : null;
    if (et0Row && et0Row.v != null) et0 = parseFloat(et0Row.v);

    let effectiveMm = 0;
    const effRow = this.configRepository
      ? await tryQuery([
          'SELECT effective_rainfall_mm AS v FROM ros_smartfarm.weekly_effective_rainfall WHERE zone_id = $1 AND week_number = $2 AND year = $3'
        ], [1, calendarWeek, calendarYear])
      : null;
    if (effRow && effRow.v != null) effectiveMm = parseFloat(effRow.v);

    const grossMm = et0 * kc;
    const netMm = Math.max(0, grossMm - (effectiveMm || 0));
    const netMmRounded = Math.round(netMm * 100) / 100; // align rounding with expected demand
    const demandM3 = Math.max(0, netMmRounded * areaRai * 1.6);

    const demand = {
      plotId,
      date,
      demandCubicMeters: demandM3,
      cropType: cropType,
      growthStage: 'auto',
      et0: et0,
      kc: kc,
      effectiveRainfall: effectiveMm || 0
    };

    await this.planningRepository.saveWaterDemand(demand);
    return demand;
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
      if (this.mode === 'internal' || !this.waterPlanningUrl) {
        const demand = await this.calculateDailyDemandInternal(plotId, date);
        this.demandCache.set(cacheKey, demand);
        return demand;
      }

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
        demandCubicMeters: this.extractDemandM3(demandOutput),
        cropType: plotConfig.cropType,
        growthStage: 'mid-season', // Simplified for now
        et0: demandOutput.et0_mm || 4.5,
        kc: demandOutput.avg_kc_factor || 1.1,
        effectiveRainfall: demandOutput.effective_rainfall_m3 || 0
      };

      this.demandCache.set(cacheKey, demand);
      logger.info({ plotId, date, demandCubicMeters: demand.demandCubicMeters }, 'Water demand calculated');
      return demand;
    } catch (error) {
      logger.error({ error, plotId, date }, 'Failed to calculate water demand');
      throw error;
    }
  }

  async syncToTimescale(demands) {
    for (const demand of demands) {
      try {
        await this.planningRepository.saveWaterDemand(demand);

        logger.info(
          { plotId: demand.plotId, date: demand.date },
          'Water demand saved'
        );
      } catch (error) {
        logger.error({ error, demand }, 'Failed to save water demand');
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

      await this.planningRepository.saveDailyProgress(
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
    return await this.planningRepository.getPlannedDemand(plotId, date);
  }

  async calculateAllPlotsDemand(date) {
    const demands = [];

    for (const plotConfig of this.plotConfigs) {
      try {
        const demand = await this.calculateDailyDemand(plotConfig.plotId, date);
        if (demand && demand.demandCubicMeters != null) {
          demands.push(demand);
        } else {
          logger.info({ plotId: plotConfig.plotId }, 'Skipped demand (insufficient data)');
        }
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

  // --- Kc resolution helpers ---
  async getKcForExactCrop(cropType, cropWeek) {
    if (!this.configRepository || !cropType || !Number.isFinite(cropWeek)) {
      return null;
    }
    const sql = `SELECT kc.kc_value
      FROM ros_smartfarm.kc_weekly kc
      JOIN ros_smartfarm.crop_ros_mapping crm ON kc.ros_type = crm.ros_type
      WHERE crm.crop_type = $1 AND kc.crop_week = $2
      LIMIT 1`;
    try {
      const { rows } = await this.configRepository.pool.query(sql, [cropType, cropWeek]);
      if (rows && rows.length) {
        const r = rows[0];
        const v = r.kc_value != null ? r.kc_value : r.v;
        const num = Number(v);
        return Number.isFinite(num) ? num : null;
      }
    } catch (_e) {
      // ignore
    }
    return null;
  }

  async getMaxWeekForCrop(cropType) {
    if (!this.configRepository || !cropType) return null;
    const sql = `SELECT MAX(kc.crop_week) AS max_week
      FROM ros_smartfarm.kc_weekly kc
      JOIN ros_smartfarm.crop_ros_mapping crm ON kc.ros_type = crm.ros_type
      WHERE crm.crop_type = $1`;
    try {
      const { rows } = await this.configRepository.pool.query(sql, [cropType]);
      if (rows && rows.length) {
        const raw = rows[0].max_week;
        if (raw == null) return null; // no mapping/data for this cropType
        const num = Number(raw);
        return Number.isFinite(num) ? num : null;
      }
    } catch (_e) {
      // ignore
    }
    return null;
  }

  async resolveKcWithTokens(cropType, cropWeek) {
    // Build candidate crop strings: tokens first, then alias, then exact, then no-space
    const aliasMap = new Map([
      ['ข้าวหอมมะลิ 105', 'ข้าวขาวดอกมะลิ105'],
      ['ข้าวหอมมะลิ105', 'ข้าวขาวดอกมะลิ105']
    ]);
    const tokens = tokenizeCropType(cropType);
    const noSpace = (cropType || '').replace(/\s+/g, '');
    const alias = aliasMap.get(cropType) || aliasMap.get(noSpace);
    const candidates = ([])
      .concat(tokens)
      .concat(alias ? [alias] : [])
      .concat([cropType])
      .concat(noSpace && noSpace !== cropType ? [noSpace] : []);

    // Evaluate max weeks for candidates (ignore those without data)
    const maxima = [];
    for (const c of candidates) {
      const m = await this.getMaxWeekForCrop(c);
      if (Number.isFinite(m)) maxima.push({ crop: c, max: m });
    }

    // If we have any finite maxima and ALL of them are exceeded, it's over-max
    if (maxima.length > 0 && maxima.every((x) => cropWeek > x.max)) {
      return { kc: 0, reason: 'over-max-week' };
    }

    // Try Kc lookup in candidate order
    for (const c of candidates) {
      const v = await this.getKcForExactCrop(c, cropWeek);
      if (v != null) return { kc: v, reason: c === cropType ? 'exact' : 'token' };
    }

    // Default fallback when no candidate matched
    return { kc: 1.1, reason: 'default' };
  }
}

module.exports = { WaterPlanningService };
