class RealtimeControlService {
  constructor(repository, valveCommandService, logger, options = {}) {
    this.repository = repository;
    this.valveCommandService = valveCommandService;
    this.logger = logger;

    const configuredWindow = options.moistureFreshnessWindowMs ?? 300000;

    if (Number.isNaN(configuredWindow) || configuredWindow < 0) {
      this.logger.warn(
        { configuredWindow },
        'Invalid moistureFreshnessWindowMs, using default 300000ms'
      );
      this.moistureFreshnessWindowMs = 300000;
    } else {
      this.moistureFreshnessWindowMs = configuredWindow;
    }
  }

  getReadingAge(timestamp) {
    const timestampDate =
      timestamp instanceof Date ? timestamp : new Date(timestamp);
    const timestampMs = timestampDate.getTime();

    if (Number.isNaN(timestampMs)) {
      return NaN;
    }

    return Date.now() - timestampMs;
  }

  isReadingFresh(timestamp) {
    return this.getReadingAge(timestamp) <= this.moistureFreshnessWindowMs;
  }

  evaluateControlDecision({ value, sensorType, thresholds, currentState }) {
    if (!thresholds) {
      throw new Error('Thresholds required');
    }

    if (!['moisture', 'water_level'].includes(sensorType)) {
      throw new Error(`Invalid sensor type: ${sensorType}`);
    }

    let lower, upper;

    if (sensorType === 'moisture') {
      lower = thresholds.moistureLowerThreshold;
      upper = thresholds.moistureUpperThreshold;
    } else {
      lower = thresholds.waterLevelLowerThreshold;
      upper = thresholds.waterLevelUpperThreshold;
    }

    if (lower >= upper) {
      throw new Error('Invalid thresholds: lower must be less than upper');
    }

    if (sensorType === 'moisture' && (value < 0 || value > 100)) {
      return {
        action: 'MAINTAIN',
        newState: currentState || 'OFF',
        reason: `Invalid sensor reading: ${value}%`,
        value,
        thresholds: { lower, upper }
      };
    }

    if (sensorType === 'water_level' && value < 0) {
      return {
        action: 'MAINTAIN',
        newState: currentState || 'OFF',
        reason: `Invalid sensor reading: ${value} cm`,
        value,
        thresholds: { lower, upper }
      };
    }

    if (sensorType === 'water_level' && value > 100) {
      return {
        action: 'TURN_OFF',
        newState: 'OFF',
        reason: `Water level overflow detected: ${value} cm`,
        value,
        thresholds: { lower, upper }
      };
    }

    let action, newState, reason;

    if (value <= lower) {
      action = 'TURN_ON';
      newState = 'ON';
      reason = `${sensorType === 'moisture' ? 'Moisture' : 'Water level'} ${value}${sensorType === 'moisture' ? '%' : ' cm'} below lower threshold ${lower}${sensorType === 'moisture' ? '%' : ' cm'}`;
    } else if (value >= upper) {
      action = 'TURN_OFF';
      newState = 'OFF';
      reason = `${sensorType === 'moisture' ? 'Moisture' : 'Water level'} ${value}${sensorType === 'moisture' ? '%' : ' cm'} above upper threshold ${upper}${sensorType === 'moisture' ? '%' : ' cm'}`;
    } else {
      action = 'MAINTAIN';
      newState = currentState || 'OFF';
      reason = `${sensorType === 'moisture' ? 'Moisture' : 'Water level'} ${value}${sensorType === 'moisture' ? '%' : ' cm'} within acceptable range (${lower}-${upper})`;
    }

    return {
      action,
      newState,
      reason,
      value,
      thresholds: { lower, upper }
    };
  }

  async handleSensorReading({ sensorId, value, timestamp, sensorType }) {
    const pool = this.repository.pool;

    try {
      if (sensorType === 'moisture') {
        const ageMs = this.getReadingAge(timestamp);

        if (Number.isNaN(ageMs)) {
          this.logger.warn(
            { sensorId, timestamp },
            'Invalid moisture timestamp: unable to determine age'
          );
          return;
        }

        if (!this.isReadingFresh(timestamp)) {
          this.logger.warn(
            { sensorId, ageMs },
            'Stale moisture reading ignored: data too old for control decision'
          );
          return;
        }
      }

      const mapping = await this.repository.getSensorPlotMapping(
        pool,
        sensorId
      );

      if (!mapping) {
        this.logger.warn({ sensorId }, 'Sensor not mapped to any plot');
        return;
      }

      const thresholds = await this.repository.getControlThresholds(
        pool,
        mapping.plotId
      );

      if (!thresholds) {
        this.logger.warn(
          { plotId: mapping.plotId },
          'Plot has no configured thresholds'
        );
        return;
      }

      const valveState = await this.repository.getValveState(
        pool,
        mapping.plotId
      );

      const decision = this.evaluateControlDecision({
        value,
        sensorType,
        thresholds,
        currentState: valveState.currentState
      });

      const logId = await this.repository.logControlDecision(pool, {
        plotId: mapping.plotId,
        sensorId,
        sensorType,
        action: decision.action,
        reason: decision.reason,
        sensorValue: value,
        lowerThreshold: decision.thresholds.lower,
        upperThreshold: decision.thresholds.upper,
        previousState: valveState.currentState,
        newState: decision.newState,
        valveCommandSent: decision.action !== 'MAINTAIN'
      });

      if (decision.action !== 'MAINTAIN') {
        try {
          await this.executeValveCommandWithRetry(
            pool,
            mapping.plotId,
            decision,
            timestamp,
            logId
          );

          await this.repository.updateDecisionLogResult(pool, logId, true);

          this.logger.info(
            {
              plotId: mapping.plotId,
              action: decision.action,
              value,
              sensorType
            },
            'Control action executed successfully'
          );
        } catch (error) {
          await this.repository.updateDecisionLogResult(
            pool,
            logId,
            false,
            error.message
          );

          this.logger.error(
            {
              error,
              plotId: mapping.plotId,
              action: decision.action
            },
            'Failed to execute control action'
          );
        }
      } else {
        this.logger.info(
          {
            plotId: mapping.plotId,
            value,
            sensorType,
            currentState: valveState.currentState
          },
          'No action required'
        );
      }
    } catch (error) {
      this.logger.error(
        {
          error,
          sensorId,
          value,
          timestamp
        },
        'Failed to handle sensor reading'
      );
    }
  }

  async executeValveCommandWithRetry(
    pool,
    plotId,
    decision,
    timestamp,
    _logId
  ) {
    const level = decision.action === 'TURN_ON' ? 100 : 0;

    await this.valveCommandService.sendValveCommandWithRetry(
      plotId,
      level,
      timestamp,
      decision.reason
    );

    await this.repository.updateValveState(
      pool,
      plotId,
      decision.newState,
      decision.reason
    );
  }
}

module.exports = { RealtimeControlService };
