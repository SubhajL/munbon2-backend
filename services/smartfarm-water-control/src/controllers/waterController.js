const logger = require('../utils/logger');

class WaterController {
  constructor(services) {
    this.controlMode = services.controlMode;
    this.moistureControl = services.moistureControl;
    this.awdControl = services.awdControl;
    this.valveCommand = services.valveCommand;
    this.valveAudit = services.valveAudit || null;
    this.waterPlanning = services.waterPlanning;
    this.waterBalance = services.waterBalance;
    this.sensorData = services.sensorData;
    this.repository = services.timescaleRepository;
    this.config = services.config;
  }

  async processPlot(plotConfig) {
    try {
      const { plotId, sensorId } = plotConfig;

      // Get control mode from database
      const controlMode = this.controlMode.getMode(plotId);
      if (!controlMode || String(controlMode).trim() === '' || String(controlMode).toLowerCase() === 'none') {
        logger.info({ plotId }, 'Skipping plot without control_mode');
        return null;
      }

      logger.info({ plotId, controlMode }, 'Processing plot');

      // Get thresholds from database once (also carries moisture_layer)
      const thresholds = await this.repository.getControlThresholds(
        this.repository.pool,
        plotId
      );

      // Get current sensor reading (respect moisture layer only for MOISTURE mode)
      let sensorReading;
      if (controlMode === 'MOISTURE') {
        sensorReading = await this.sensorData.getSensorReading(sensorId, {
          moistureLayer: thresholds?.moistureLayer || 'surface'
        });
      } else {
        sensorReading = await this.sensorData.getSensorReading(sensorId);
      }

      if (!sensorReading) {
        logger.warn({ plotId, sensorId }, 'No sensor reading available');
        return null;
      }

      // Get current valve status
      const currentValveStatus = await this.valveCommand.getValveStatus(plotId);

      if (!thresholds) {
        logger.warn({ plotId }, 'No thresholds configured for plot');
        return {
          action: 'MAINTAIN',
          reason: 'No thresholds configured'
        };
      }

      let decision;
      if (controlMode === 'MOISTURE') {
        decision = await this.processMoistureControl(
          plotConfig,
          sensorReading,
          currentValveStatus,
          thresholds
        );
      } else if (controlMode === 'AWD') {
        decision = await this.processAWDControl(
          plotConfig,
          sensorReading,
          currentValveStatus,
          thresholds
        );
      } else {
        throw new Error(`Unknown control mode: ${controlMode}`);
      }

      // Execute valve command if needed
      if (decision.action !== 'MAINTAIN') {
        await this.executeValveCommand(plotConfig, decision, {
          controlMode,
          sensorReading,
          thresholds,
          valveState: currentValveStatus
        });
      }

      return decision;
    } catch (error) {
      logger.error(
        { error, plotId: plotConfig.plotId },
        'Failed to process plot'
      );
      throw error;
    }
  }

  async processMoistureControl(
    plotConfig,
    sensorReading,
    currentValveStatus,
    thresholds
  ) {
    const { plotId } = plotConfig;
    const moisturePercent = sensorReading.value;

    const decision = this.moistureControl.evaluateMoistureStatus(
      plotId,
      moisturePercent,
      thresholds.moistureLowerThreshold,
      thresholds.moistureUpperThreshold
    );

    // Track irrigation cycles
    if (decision.action === 'ON' && currentValveStatus.status !== 'ON') {
      this.waterBalance.startIrrigation(
        plotId,
        plotConfig.valveName,
        'MOISTURE',
        moisturePercent
      );
    } else if (
      decision.action === 'OFF' &&
      currentValveStatus.status === 'ON'
    ) {
      await this.waterBalance.stopIrrigation(plotId);
    }

    return decision;
  }

  async processAWDControl(
    plotConfig,
    sensorReading,
    currentValveStatus,
    thresholds
  ) {
    const { plotId } = plotConfig;
    const waterLevelCm = sensorReading.value;

    // Pass thresholds explicitly without mutating state
    const thresholdOverrides = {
      minWaterLevelCm: thresholds.waterLevelLowerThreshold,
      maxWaterLevelCm: thresholds.waterLevelUpperThreshold
    };

    const decision = this.awdControl.evaluateAWDStatus(
      plotId,
      waterLevelCm,
      thresholdOverrides
    );

    // Track irrigation cycles
    if (decision.action === 'ON' && currentValveStatus.status !== 'ON') {
      this.waterBalance.startIrrigation(
        plotId,
        plotConfig.valveName,
        'AWD',
        waterLevelCm
      );
      this.awdControl.recordIrrigationStart(plotId);
    } else if (
      decision.action === 'OFF' &&
      currentValveStatus.status === 'ON'
    ) {
      await this.waterBalance.stopIrrigation(plotId);
    }

    return decision;
  }

  async executeValveCommand(plotConfig, decision, context = {}) {
    const { plotId } = plotConfig;
    const level = decision.action === 'ON' ? 1 : 0;
    const timestamp = new Date();

    let auditId = null;
    const auditService = this.valveAudit;
    const controlMode = context.controlMode || 'MOISTURE';
    const sensorReading = context.sensorReading || {};
    const thresholds = context.thresholds || {};
    const valveState = context.valveState || {};
    const valveName =
      plotConfig.valveName ||
      (this.valveCommand.valveMapping
        ? this.valveCommand.valveMapping.get(plotId)
        : undefined) ||
      'UNKNOWN';
    const auditAction =
      decision.action === 'ON'
        ? 'TURN_ON'
        : decision.action === 'OFF'
        ? 'TURN_OFF'
        : decision.action;

    if (auditService) {
      try {
        auditId = await auditService.logValveChange({
          plotId,
          valveName,
          changedAt: timestamp,
          previousState: valveState.status || 'UNKNOWN',
          newState: decision.action === 'ON' ? 'ON' : 'OFF',
          moistureValue:
            controlMode === 'MOISTURE' ? sensorReading.value ?? null : null,
          waterLevelValue:
            controlMode === 'AWD' ? sensorReading.value ?? null : null,
          sensorId: plotConfig.sensorId || sensorReading.sensorId || null,
          sensorTimestamp: sensorReading.timestamp || timestamp,
          controlMode,
          moistureLowerThreshold: thresholds.moistureLowerThreshold || null,
          moistureUpperThreshold: thresholds.moistureUpperThreshold || null,
          waterLevelLowerThreshold:
            thresholds.waterLevelLowerThreshold || null,
          waterLevelUpperThreshold:
            thresholds.waterLevelUpperThreshold || null,
          action: auditAction,
          reason: decision.reason,
          valveCommandSent: true,
          mssqlTableUsed: this.valveCommand.tableName || null,
          triggeredBy: 'SCHEDULED'
        });
      } catch (auditError) {
        logger.error(
          { error: auditError, plotId, valveName },
          'Failed to log valve change for cron command'
        );
      }
    }

    try {
      await this.valveCommand.sendValveCommand(
        plotId,
        level,
        timestamp,
        decision.reason
      );

      if (auditService && auditId) {
        await auditService.updateCommandResult(auditId, true, null);
      }
    } catch (error) {
      if (auditService && auditId) {
        await auditService.updateCommandResult(auditId, false, error.message);
      }
      throw error;
    }

    logger.info(
      {
        plotId,
        action: decision.action,
        reason: decision.reason
      },
      'Valve command executed'
    );
  }

  async runControlLoop() {
    logger.info('Starting control loop');

    for (const plotConfig of this.config.plots) {
      try {
        await this.processPlot(plotConfig);
      } catch (error) {
        logger.error(
          { error, plotId: plotConfig.plotId },
          'Failed to process plot in control loop'
        );
        // Continue with next plot
      }
    }

    logger.info('Control loop completed');
  }

  async runPlanningLoop() {
    logger.info('Starting planning loop');

    try {
      const today = new Date();
      today.setHours(0, 0, 0, 0);

      // Calculate water demand for all plots
      const demands = await this.waterPlanning.calculateAllPlotsDemand(today);

      // Sync to TimescaleDB
      await this.waterPlanning.syncToTimescale(demands);

      // Seed daily_progress rows with 0 actual usage (updated later by progress job)
      for (const d of demands) {
        try {
          await this.waterPlanning.updateDailyProgress(d.plotId, 0, today);
        } catch (e) {
          logger.warn({ error: e, plotId: d.plotId }, 'Failed to seed daily_progress');
        }
      }

      logger.info(
        { count: demands.length },
        'Water demands calculated and synced'
      );
    } catch (error) {
      logger.error({ error }, 'Failed to run planning loop');
      throw error;
    }
  }

  async updateDailyProgress() {
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    for (const plotConfig of this.config.plots) {
      try {
        // Get today's water usage
        const balance = await this.waterBalance.calculateDailyBalance(
          plotConfig.plotId,
          today
        );

        // Convert liters to cubic meters
        const actualUsageM3 = balance.totalUsageLiters / 1000;

        // Update progress
        await this.waterPlanning.updateDailyProgress(
          plotConfig.plotId,
          actualUsageM3,
          today
        );
      } catch (error) {
        logger.error(
          { error, plotId: plotConfig.plotId },
          'Failed to update daily progress'
        );
      }
    }
  }

  async getPlotStatus(plotId) {
    const plotConfig = this.config.plots.find((p) => p.plotId === plotId);
    if (!plotConfig) {
      throw new Error(`Plot not found: ${plotId}`);
    }

    const [valveStatus, sensorReading, todayBalance] = await Promise.all([
      this.valveCommand.getValveStatus(plotId),
      this.sensorData.getSensorReading(plotConfig.sensorId),
      this.waterBalance.calculateDailyBalance(plotId, new Date())
    ]);

    return {
      plotId,
      controlMode: plotConfig.controlMode,
      valve: valveStatus,
      sensor: sensorReading,
      todayUsage: todayBalance
    };
  }
}

module.exports = { WaterController };
