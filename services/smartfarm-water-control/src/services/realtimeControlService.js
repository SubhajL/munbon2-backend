class RealtimeControlService {
  constructor(
    repository,
    valveCommandService,
    logger,
    options = {},
    valveAuditService = null
  ) {
    this.repository = repository;
    this.valveCommandService = valveCommandService;
    this.logger = logger;
    this.valveAuditService = valveAuditService;

    // Optional separate repository for writing sensor_plot_readings (e.g., config DB)
    this.readingsRepository = options.readingsRepository || repository;

    // Optional geo-spatial resolver for water level sensors
    this.geoSpatialResolver = options.geoSpatialResolver || null;

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

  /**
   * Normalize sensor ID from gateway-sensor format (0001-0001) to 8-digit format (00000001)
   * for DB lookup in sensor_plot_mapping and sensor_plot_readings tables.
   * @param {string} sensorId - Raw sensor ID from notification payload
   * @returns {string} Normalized 8-digit sensor ID
   */
  normalizeSensorId(sensorId) {
    if (!sensorId || typeof sensorId !== 'string') return sensorId;
    // Match pattern: gatewayID-sensorID (e.g., 0001-0001, 0001-0002, 0001-0010)
    const match = sensorId.match(/^\d{4}-(\d{4})$/);
    if (match) {
      // Extract sensor part and pad to 8 digits
      const sensorPart = match[1];
      return sensorPart.padStart(8, '0');
    }
    // Already 8-digit or other format: return as-is
    return sensorId;
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

  async handleSensorReading({
    sensorId,
    value,
    timestamp,
    sensorType,
    locationLat,
    locationLng
  }) {
    const configPool = this.readingsRepository.pool;
    const controlPool = this.repository.pool;

    try {
      // Normalize sensor ID: 0001-0001 → 00000001 for DB lookup
      const normalizedSensorId = this.normalizeSensorId(sensorId);
      if (normalizedSensorId !== sensorId) {
        this.logger.debug(
          { rawSensorId: sensorId, normalizedSensorId },
          'Normalized sensor ID for DB lookup'
        );
      }

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

      let mapping = await this.readingsRepository.getSensorPlotMapping(
        configPool,
        normalizedSensorId
      );

      // For water_level sensors without mapping, try geo-spatial resolution
      if (!mapping && sensorType === 'water_level' && this.geoSpatialResolver) {
        if (
          typeof locationLat === 'number' &&
          typeof locationLng === 'number'
        ) {
          this.logger.info(
            { sensorId: normalizedSensorId, locationLat, locationLng },
            'Water level sensor not mapped: attempting geo-spatial resolution'
          );

          const resolution = await this.geoSpatialResolver.resolveAndMapSensor({
            sensorId: normalizedSensorId,
            longitude: locationLng,
            latitude: locationLat,
            sensorType
          });

          if (resolution) {
            this.logger.info(
              {
                sensorId: normalizedSensorId,
                plotId: resolution.plotId,
                wasCreated: resolution.wasCreated
              },
              'Geo-spatial resolution successful'
            );

            // Re-fetch mapping after creation
            mapping = await this.readingsRepository.getSensorPlotMapping(
              configPool,
              normalizedSensorId
            );
          }
        }
      }

      if (!mapping) {
        this.logger.warn(
          { sensorId, normalizedSensorId, sensorType },
          'Sensor not mapped to any plot'
        );
        return;
      }

      const thresholds = await this.readingsRepository.getControlThresholds(
        configPool,
        mapping.plotId
      );

      if (!thresholds) {
        this.logger.warn(
          { plotId: mapping.plotId },
          'Plot has no configured thresholds'
        );
        return;
      }

      const valveState = await this.readingsRepository.getValveState(
        configPool,
        mapping.plotId
      );

      // Persist latest reading snapshot for monitoring
      try {
        // First, clean up any stale readings for this sensor in other plots
        // (handles case where sensor physically moved between plots)
        const stalePlots =
          await this.readingsRepository.deleteStaleReadingsForSensor(
            this.readingsRepository.pool,
            {
              sensorId: normalizedSensorId,
              sensorType,
              currentPlotId: mapping.plotId
            }
          );

        if (stalePlots.length > 0) {
          this.logger.info(
            {
              sensorId: normalizedSensorId,
              stalePlots,
              currentPlot: mapping.plotId
            },
            'Cleaned up stale sensor readings from previous plots'
          );
        }

        // Fetch all fresh sensor readings for this plot and sensor type
        const freshReadings =
          await this.readingsRepository.getFreshSensorReadingsForPlot(
            this.readingsRepository.pool,
            {
              plotId: mapping.plotId,
              sensorType
            }
          );

        let readingToStore;

        if (freshReadings.length >= 2) {
          // Multiple sensors: compute average
          const sensorIds = freshReadings.map((r) => r.sensorId);
          const values = freshReadings.map((r) => r.value);
          const avgValue =
            values.reduce((sum, v) => sum + v, 0) / values.length;

          readingToStore = {
            plotId: mapping.plotId,
            sensorId: `AVG_${freshReadings.length}_sensors`,
            sensorType,
            value: avgValue,
            units: sensorType === 'moisture' ? '%' : 'cm',
            timestamp,
            contributingSensorIds: sensorIds
          };

          this.logger.info(
            {
              plotId: mapping.plotId,
              sensorType,
              contributingSensors: sensorIds,
              individualValues: values,
              averageValue: avgValue
            },
            'Computed average from multiple sensors'
          );
        } else {
          // Single sensor or no other fresh readings: use raw value
          readingToStore = {
            plotId: mapping.plotId,
            sensorId: normalizedSensorId,
            sensorType,
            value,
            units: sensorType === 'moisture' ? '%' : 'cm',
            timestamp,
            contributingSensorIds: [normalizedSensorId]
          };
        }

        await this.readingsRepository.upsertSensorPlotReading(
          this.readingsRepository.pool,
          readingToStore
        );
      } catch (e) {
        this.logger.warn(
          {
            error: e,
            rawSensorId: sensorId,
            normalizedSensorId,
            plotId: mapping.plotId
          },
          'Failed to upsert sensor_plot_readings'
        );
      }

      const decision = this.evaluateControlDecision({
        value,
        sensorType,
        thresholds,
        currentState: valveState.currentState
      });

      const logId = await this.repository.logControlDecision(controlPool, {
        plotId: mapping.plotId,
        sensorId: normalizedSensorId,
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
        let auditId = null;

        try {
          // Log to audit table before executing command
          if (this.valveAuditService) {
            const valveName = this.valveCommandService.valveMapping.get(
              mapping.plotId
            );
            const config = await this.repository.getPlotConfiguration(
              mapping.plotId
            );

            const controlMode =
              config?.controlMode ||
              (sensorType === 'moisture' ? 'MOISTURE' : 'AWD');

            auditId = await this.valveAuditService.logValveChange({
              plotId: mapping.plotId,
              valveName: valveName || 'UNKNOWN',
              changedAt: new Date(),
              previousState: valveState.currentState || 'UNKNOWN',
              newState: decision.newState,
              moistureValue: sensorType === 'moisture' ? value : null,
              waterLevelValue: sensorType === 'water_level' ? value : null,
              sensorId: normalizedSensorId,
              sensorTimestamp: timestamp,
              controlMode,
              moistureLowerThreshold: thresholds.moistureLowerThreshold,
              moistureUpperThreshold: thresholds.moistureUpperThreshold,
              waterLevelLowerThreshold: thresholds.waterLevelLowerThreshold,
              waterLevelUpperThreshold: thresholds.waterLevelUpperThreshold,
              action: decision.action,
              reason: decision.reason,
              valveCommandSent: true,
              mssqlTableUsed: this.valveCommandService.tableName,
              triggeredBy: 'AUTO'
            });
          }

          await this.executeValveCommandWithRetry(
            configPool,
            mapping.plotId,
            decision,
            timestamp,
            logId
          );

          await this.repository.updateDecisionLogResult(
            controlPool,
            logId,
            true
          );

          // Update audit with success
          if (this.valveAuditService && auditId) {
            await this.valveAuditService.updateCommandResult(auditId, true);
          }

          this.logger.info(
            {
              plotId: mapping.plotId,
              action: decision.action,
              value,
              sensorType,
              auditId
            },
            'Control action executed successfully'
          );
        } catch (error) {
          await this.repository.updateDecisionLogResult(
            controlPool,
            logId,
            false,
            error.message
          );

          // Update audit with failure
          if (this.valveAuditService && auditId) {
            await this.valveAuditService.updateCommandResult(
              auditId,
              false,
              error.message
            );
          }

          this.logger.error(
            {
              error,
              plotId: mapping.plotId,
              action: decision.action,
              auditId
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
    const level = decision.action === 'TURN_ON' ? 1 : 0;

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
