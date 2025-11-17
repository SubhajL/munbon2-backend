const logger = require('../utils/logger');

class MoistureControlService {
  constructor(config) {
    this.config = config;
  }

  evaluateMoistureStatus(plotId, moisturePercent, thresholdLow, thresholdHigh) {
    const metadata = {};

    // Validate moisture reading
    if (moisturePercent < 0 || moisturePercent > 100) {
      metadata.warning = 'Invalid moisture reading';
    }

    let action;
    let reason;

    if (moisturePercent < thresholdLow) {
      action = 'ON';
      reason = 'Moisture below low threshold';
    } else if (moisturePercent > thresholdHigh) {
      action = 'OFF';
      reason = 'Moisture above high threshold';
    } else {
      action = 'MAINTAIN';
      reason = 'Moisture within acceptable range';
    }

    const decision = {
      plotId,
      timestamp: new Date(),
      action,
      reason,
      currentValue: moisturePercent,
      thresholds: {
        low: thresholdLow,
        high: thresholdHigh
      }
    };

    if (Object.keys(metadata).length > 0) {
      decision.metadata = metadata;
    }

    logger.info(
      {
        plotId,
        action,
        moisturePercent,
        thresholdLow,
        thresholdHigh
      },
      'Moisture control decision made'
    );

    return decision;
  }

  getValveAction(
    currentMoisture,
    currentValveState,
    lowThreshold,
    highThreshold
  ) {
    if (currentMoisture < lowThreshold) {
      return 'ON';
    } else if (currentMoisture > highThreshold) {
      return 'OFF';
    } else {
      return 'MAINTAIN';
    }
  }

  shouldIrrigate(action) {
    return action === 'ON';
  }

  calculateIrrigationDuration(currentMoisture, lowThreshold, highThreshold) {
    const targetMoisture = (lowThreshold + highThreshold) / 2;
    const deficit = targetMoisture - currentMoisture;

    if (deficit <= 0) {
      return 0;
    }

    // Estimate: 10 minutes per 1% moisture deficit
    const estimatedMinutes = deficit * 10;

    // Cap at 60 minutes maximum
    return Math.min(estimatedMinutes, 60);
  }

  async executeMoistureIrrigation(plotId, valveAction, valveCommandService) {
    try {
      if (valveAction === 'MAINTAIN') {
        return { success: true, message: 'No action needed' };
      }

      const level = valveAction === 'ON' ? 1 : 0;
      const result = await valveCommandService.sendValveCommand(
        plotId,
        level,
        new Date(),
        `Moisture control: ${valveAction}`
      );

      return result;
    } catch (error) {
      logger.error(
        { error, plotId, valveAction },
        'Failed to execute moisture irrigation'
      );
      throw error;
    }
  }
}

module.exports = { MoistureControlService };
