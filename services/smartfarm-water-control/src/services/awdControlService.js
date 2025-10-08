const logger = require("../utils/logger");

class AWDControlService {
  constructor(config) {
    this.config = config;
    this.lastIrrigationDates = new Map();
  }

  evaluateAWDStatus(plotId, waterLevelCm, thresholdOverrides = null) {
    const metadata = {};

    // Use overrides if provided, otherwise fall back to config
    const minWaterLevelCm =
      thresholdOverrides?.minWaterLevelCm ?? this.config.minWaterLevelCm;
    const maxWaterLevelCm =
      thresholdOverrides?.maxWaterLevelCm ?? this.config.maxWaterLevelCm;

    // Validate water level reading
    if (waterLevelCm < 0) {
      metadata.warning = "Negative water level reading";
    } else if (waterLevelCm > 50) {
      metadata.warning = "Unusually high water level";
    }

    let action;
    let reason;

    if (waterLevelCm < minWaterLevelCm) {
      action = "ON";
      reason = "Water level below minimum threshold";
    } else if (waterLevelCm >= maxWaterLevelCm) {
      action = "OFF";
      reason = "Water level at or above maximum threshold";
    } else {
      action = "MAINTAIN";
      reason = "Water level within acceptable range";
    }

    const decision = {
      plotId,
      timestamp: new Date(),
      action,
      reason,
      currentValue: waterLevelCm,
      thresholds: {
        min: minWaterLevelCm,
        max: maxWaterLevelCm,
      },
    };

    if (Object.keys(metadata).length > 0) {
      decision.metadata = metadata;
    }

    logger.info(
      {
        plotId,
        action,
        waterLevelCm,
        phase: this.getAWDPhase(
          waterLevelCm,
          action === "ON",
          plotId,
          thresholdOverrides,
        ),
      },
      "AWD control decision made",
    );

    return decision;
  }

  calculateAWDTarget(_plotId, _currentLevelCm, thresholdOverrides = null) {
    // Always target maximum water level for AWD
    const maxWaterLevelCm =
      thresholdOverrides?.maxWaterLevelCm ?? this.config.maxWaterLevelCm;
    return maxWaterLevelCm;
  }

  shouldStartDryingCycle(
    plotId,
    currentWaterLevelCm,
    thresholdOverrides = null,
  ) {
    const minWaterLevelCm =
      thresholdOverrides?.minWaterLevelCm ?? this.config.minWaterLevelCm;

    // Don't dry if water is already low
    if (currentWaterLevelCm <= minWaterLevelCm + 2) {
      return false;
    }

    const lastIrrigation = this.lastIrrigationDates.get(plotId);
    if (!lastIrrigation) {
      return false;
    }

    const daysSinceIrrigation =
      (Date.now() - lastIrrigation.getTime()) / (1000 * 60 * 60 * 24);
    return daysSinceIrrigation >= this.config.dryingPeriodDays;
  }

  calculateFlowRate(waterLevelReadings, areaSquareMeters) {
    if (!waterLevelReadings || waterLevelReadings.length < 2) {
      return 0;
    }

    const firstReading = waterLevelReadings[0];
    const lastReading = waterLevelReadings[waterLevelReadings.length - 1];

    const levelChangeCm = lastReading.waterLevelCm - firstReading.waterLevelCm;
    const timeMinutes =
      (lastReading.timestamp - firstReading.timestamp) / (1000 * 60);

    if (timeMinutes <= 0) {
      return 0;
    }

    // Convert cm water level change to volume
    const volumeCubicMeters = (levelChangeCm / 100) * areaSquareMeters;
    const volumeLiters = volumeCubicMeters * 1000;

    // Calculate flow rate in liters per minute
    return Math.round(volumeLiters / timeMinutes);
  }

  getAWDPhase(
    waterLevelCm,
    isIrrigating,
    plotId = null,
    thresholdOverrides = null,
  ) {
    if (isIrrigating) {
      return "flooding";
    }

    const minWaterLevelCm =
      thresholdOverrides?.minWaterLevelCm ?? this.config.minWaterLevelCm;

    if (waterLevelCm >= minWaterLevelCm + 5) {
      return "flooded";
    }

    if (waterLevelCm <= minWaterLevelCm) {
      return "dried";
    }

    // Check if in drying phase
    if (plotId && this.lastIrrigationDates.has(plotId)) {
      return "drying";
    }

    return "drying";
  }

  recordIrrigationStart(plotId) {
    this.lastIrrigationDates.set(plotId, new Date());
    logger.info({ plotId }, "AWD irrigation cycle started");
  }

  async executeAWDIrrigation(plotId, targetLevelCm, valveCommandService) {
    try {
      const result = await valveCommandService.sendValveCommand(
        plotId,
        1, // ON
        new Date(),
        `AWD control: Target level ${targetLevelCm}cm`,
      );

      if (result.success) {
        this.recordIrrigationStart(plotId);
      }

      return result;
    } catch (error) {
      logger.error(
        { error, plotId, targetLevelCm },
        "Failed to execute AWD irrigation",
      );
      throw error;
    }
  }
}

module.exports = { AWDControlService };
