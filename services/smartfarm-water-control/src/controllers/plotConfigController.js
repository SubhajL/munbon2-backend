const logger = require("../utils/logger");

/**
 * Controller for plot configuration management (crop type, control mode)
 * Used by UI to configure per-plot settings
 */
class PlotConfigController {
  constructor(repository) {
    this.repository = repository;
  }

  /**
   * GET /api/plots/configurations
   * Get all plot configurations
   */
  async getAllConfigurations(req, res) {
    try {
      const configs = await this.repository.getAllPlotConfigurations();

      res.json({
        success: true,
        count: configs.length,
        data: configs,
      });
    } catch (error) {
      logger.error({ error }, "Failed to get plot configurations");
      res.status(500).json({
        success: false,
        error: "Failed to retrieve plot configurations",
      });
    }
  }

  /**
   * GET /api/plots/:plotId/configuration
   * Get configuration for a specific plot
   */
  async getConfiguration(req, res) {
    try {
      const { plotId } = req.params;

      const config = await this.repository.getPlotConfiguration(plotId);

      if (!config) {
        return res.status(404).json({
          success: false,
          error: `Configuration not found for plot ${plotId}`,
        });
      }

      res.json({
        success: true,
        data: config,
      });
    } catch (error) {
      logger.error(
        { error, plotId: req.params.plotId },
        "Failed to get plot configuration",
      );
      res.status(500).json({
        success: false,
        error: "Failed to retrieve plot configuration",
      });
    }
  }

  /**
   * PUT /api/plots/:plotId/configuration
   * Update configuration for a specific plot
   * Body: { cropType: 'rice'|'corn', controlMode: 'AWD'|'MOISTURE', updatedBy: 'username', notes?: 'optional' }
   */
  async updateConfiguration(req, res) {
    try {
      const { plotId } = req.params;
      const { cropType, controlMode, updatedBy, notes } = req.body;

      // Validation
      const validCropTypes = ["rice", "corn", "-", "durian", "banana", "durian + banana", "stevia"];
      if (!cropType || !validCropTypes.includes(cropType)) {
        return res.status(400).json({
          success: false,
          error: `Invalid cropType. Must be one of: ${validCropTypes.join(", ")}`,
        });
      }

      if (!controlMode || !["AWD", "MOISTURE", "-"].includes(controlMode)) {
        return res.status(400).json({
          success: false,
          error: "Invalid controlMode. Must be 'AWD', 'MOISTURE', or '-'",
        });
      }

      const config = await this.repository.upsertPlotConfiguration({
        plotId,
        cropType,
        controlMode,
        updatedBy,
        notes,
      });

      res.json({
        success: true,
        message: "Plot configuration updated successfully",
        data: config,
      });
    } catch (error) {
      logger.error(
        { error, plotId: req.params.plotId },
        "Failed to update plot configuration",
      );
      res.status(500).json({
        success: false,
        error: "Failed to update plot configuration",
      });
    }
  }

  /**
   * POST /api/plots/configurations/batch
   * Batch update multiple plot configurations
   * Body: { configurations: [{ plotId, cropType, controlMode, updatedBy, notes? }] }
   */
  async batchUpdateConfigurations(req, res) {
    try {
      const { configurations } = req.body;

      if (!Array.isArray(configurations) || configurations.length === 0) {
        return res.status(400).json({
          success: false,
          error: "configurations must be a non-empty array",
        });
      }

      // Validate each configuration
      for (const config of configurations) {
        if (!config.plotId || !config.cropType || !config.controlMode) {
          return res.status(400).json({
            success: false,
            error:
              "Each configuration must have plotId, cropType, and controlMode",
          });
        }

        const validCropTypes = ["rice", "corn", "-", "durian", "banana", "durian + banana", "stevia"];
        if (!validCropTypes.includes(config.cropType)) {
          return res.status(400).json({
            success: false,
            error: `Invalid cropType '${config.cropType}' for plot ${config.plotId}`,
          });
        }

        if (!["AWD", "MOISTURE", "-"].includes(config.controlMode)) {
          return res.status(400).json({
            success: false,
            error: `Invalid controlMode '${config.controlMode}' for plot ${config.plotId}`,
          });
        }
      }

      const results =
        await this.repository.batchUpsertPlotConfigurations(configurations);

      res.json({
        success: true,
        message: `Updated ${results.length} plot configurations`,
        data: results,
      });
    } catch (error) {
      logger.error({ error }, "Failed to batch update plot configurations");
      res.status(500).json({
        success: false,
        error: "Failed to batch update plot configurations",
      });
    }
  }

  /**
   * GET /api/plots/configurations/summary
   * Get summary statistics of plot configurations
   */
  async getConfigurationSummary(req, res) {
    try {
      const configs = await this.repository.getAllPlotConfigurations();

      const summary = {
        total: configs.length,
        byCropType: {},
        byControlMode: {},
        byCombination: {},
      };

      configs.forEach((config) => {
        // Count by crop type
        summary.byCropType[config.cropType] =
          (summary.byCropType[config.cropType] || 0) + 1;

        // Count by control mode
        summary.byControlMode[config.controlMode] =
          (summary.byControlMode[config.controlMode] || 0) + 1;

        // Count by combination
        const combination = `${config.cropType}-${config.controlMode}`;
        summary.byCombination[combination] =
          (summary.byCombination[combination] || 0) + 1;
      });

      res.json({
        success: true,
        data: summary,
      });
    } catch (error) {
      logger.error({ error }, "Failed to get configuration summary");
      res.status(500).json({
        success: false,
        error: "Failed to retrieve configuration summary",
      });
    }
  }
}

module.exports = PlotConfigController;
