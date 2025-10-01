const logger = require("../utils/logger");

class WaterController {
  constructor(services) {
    this.controlMode = services.controlMode;
    this.moistureControl = services.moistureControl;
    this.awdControl = services.awdControl;
    this.valveCommand = services.valveCommand;
    this.waterPlanning = services.waterPlanning;
    this.waterBalance = services.waterBalance;
    this.sensorData = services.sensorData;
    this.config = services.config;
  }

  async processPlot(plotConfig) {
    try {
      const { plotId, sensorId } = plotConfig;

      // Get control mode from database
      const controlMode = this.controlMode.getMode(plotId);

      logger.info({ plotId, controlMode }, "Processing plot");

      // Get current sensor reading
      const sensorReading = await this.sensorData.getSensorReading(sensorId);

      if (!sensorReading) {
        logger.warn({ plotId, sensorId }, "No sensor reading available");
        return null;
      }

      // Get current valve status
      const currentValveStatus = await this.valveCommand.getValveStatus(plotId);

      let decision;
      if (controlMode === "MOISTURE") {
        decision = await this.processMoistureControl(
          plotConfig,
          sensorReading,
          currentValveStatus,
        );
      } else if (controlMode === "AWD") {
        decision = await this.processAWDControl(
          plotConfig,
          sensorReading,
          currentValveStatus,
        );
      } else {
        throw new Error(`Unknown control mode: ${controlMode}`);
      }

      // Execute valve command if needed
      if (decision.action !== "MAINTAIN") {
        await this.executeValveCommand(plotConfig, decision);
      }

      return decision;
    } catch (error) {
      logger.error(
        { error, plotId: plotConfig.plotId },
        "Failed to process plot",
      );
      throw error;
    }
  }

  async processMoistureControl(plotConfig, sensorReading, currentValveStatus) {
    const { plotId } = plotConfig;
    const moisturePercent = sensorReading.value;

    const decision = this.moistureControl.evaluateMoistureStatus(
      plotId,
      moisturePercent,
      this.config.control.moisture.thresholdLowPercent,
      this.config.control.moisture.thresholdHighPercent,
    );

    // Track irrigation cycles
    if (decision.action === "ON" && currentValveStatus.status !== "ON") {
      this.waterBalance.startIrrigation(
        plotId,
        plotConfig.valveName,
        "MOISTURE",
        moisturePercent,
      );
    } else if (
      decision.action === "OFF" &&
      currentValveStatus.status === "ON"
    ) {
      await this.waterBalance.stopIrrigation(plotId);
    }

    return decision;
  }

  async processAWDControl(plotConfig, sensorReading, currentValveStatus) {
    const { plotId } = plotConfig;
    const waterLevelCm = sensorReading.value;

    const decision = this.awdControl.evaluateAWDStatus(plotId, waterLevelCm);

    // Track irrigation cycles
    if (decision.action === "ON" && currentValveStatus.status !== "ON") {
      this.waterBalance.startIrrigation(
        plotId,
        plotConfig.valveName,
        "AWD",
        waterLevelCm,
      );
      this.awdControl.recordIrrigationStart(plotId);
    } else if (
      decision.action === "OFF" &&
      currentValveStatus.status === "ON"
    ) {
      await this.waterBalance.stopIrrigation(plotId);
    }

    return decision;
  }

  async executeValveCommand(plotConfig, decision) {
    const { plotId } = plotConfig;
    const level = decision.action === "ON" ? 1 : 0;

    await this.valveCommand.sendValveCommand(
      plotId,
      level,
      new Date(),
      decision.reason,
    );

    logger.info(
      {
        plotId,
        action: decision.action,
        reason: decision.reason,
      },
      "Valve command executed",
    );
  }

  async runControlLoop() {
    logger.info("Starting control loop");

    for (const plotConfig of this.config.plots) {
      try {
        await this.processPlot(plotConfig);
      } catch (error) {
        logger.error(
          { error, plotId: plotConfig.plotId },
          "Failed to process plot in control loop",
        );
        // Continue with next plot
      }
    }

    logger.info("Control loop completed");
  }

  async runPlanningLoop() {
    logger.info("Starting planning loop");

    try {
      const today = new Date();
      today.setHours(0, 0, 0, 0);

      // Calculate water demand for all plots
      const demands = await this.waterPlanning.calculateAllPlotsDemand(today);

      // Sync to TimescaleDB
      await this.waterPlanning.syncToTimescale(demands);

      logger.info(
        { count: demands.length },
        "Water demands calculated and synced",
      );
    } catch (error) {
      logger.error({ error }, "Failed to run planning loop");
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
          today,
        );

        // Convert liters to cubic meters
        const actualUsageM3 = balance.totalUsageLiters / 1000;

        // Update progress
        await this.waterPlanning.updateDailyProgress(
          plotConfig.plotId,
          actualUsageM3,
          today,
        );
      } catch (error) {
        logger.error(
          { error, plotId: plotConfig.plotId },
          "Failed to update daily progress",
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
      this.waterBalance.calculateDailyBalance(plotId, new Date()),
    ]);

    return {
      plotId,
      controlMode: plotConfig.controlMode,
      valve: valveStatus,
      sensor: sensorReading,
      todayUsage: todayBalance,
    };
  }
}

module.exports = { WaterController };
