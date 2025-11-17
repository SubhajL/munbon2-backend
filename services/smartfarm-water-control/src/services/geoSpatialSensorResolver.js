class GeoSpatialSensorResolver {
  constructor({ repository, logger, enableAutoMapping = true }) {
    this.repository = repository;
    this.logger = logger;
    this.enableAutoMapping = enableAutoMapping;
  }

  async resolvePlotFromCoordinates(longitude, latitude) {
    if (
      typeof longitude !== 'number' ||
      typeof latitude !== 'number' ||
      longitude === null ||
      latitude === null ||
      Number.isNaN(longitude) ||
      Number.isNaN(latitude)
    ) {
      return null;
    }

    try {
      const plotId = await this.repository.findPlotByCoordinates(
        this.repository.pool,
        longitude,
        latitude
      );

      return plotId;
    } catch (error) {
      this.logger.error(
        { error, longitude, latitude },
        'Failed to resolve plot from coordinates'
      );
      throw error;
    }
  }

  async ensureSensorMapping(sensorId, plotId, sensorType) {
    const existingMapping = await this.repository.getSensorPlotMapping(
      this.repository.pool,
      sensorId
    );

    if (existingMapping && existingMapping.plotId === plotId) {
      return {
        plotId,
        wasCreated: false,
        previousPlotId: null
      };
    }

    const previousPlotId = existingMapping ? existingMapping.plotId : null;

    await this.repository.upsertSensorPlotMapping(this.repository.pool, {
      sensorId,
      plotId,
      sensorType
    });

    if (previousPlotId && previousPlotId !== plotId) {
      this.logger.info(
        { sensorId, previousPlotId, newPlotId: plotId },
        'Sensor mapping updated: sensor moved between plots'
      );
    } else {
      this.logger.info(
        { sensorId, plotId, sensorType },
        'Sensor mapping created'
      );
    }

    return {
      plotId,
      wasCreated: !existingMapping,
      previousPlotId
    };
  }

  async resolveAndMapSensor({ sensorId, longitude, latitude, sensorType }) {
    if (
      typeof longitude !== 'number' ||
      typeof latitude !== 'number' ||
      longitude === null ||
      latitude === null
    ) {
      this.logger.debug(
        { sensorId, longitude, latitude },
        'Invalid coordinates: skipping geo-spatial resolution'
      );
      return null;
    }

    const plotId = await this.resolvePlotFromCoordinates(
      longitude,
      latitude,
      sensorType
    );

    if (!plotId) {
      this.logger.warn(
        { sensorId, longitude, latitude, sensorType },
        'Sensor location outside all plot boundaries'
      );
      return null;
    }

    if (!this.enableAutoMapping) {
      this.logger.debug(
        { sensorId, plotId },
        'Auto-mapping disabled: plot resolved but not persisted'
      );
      return {
        plotId,
        sensorId,
        sensorType,
        wasCreated: false,
        previousPlotId: null
      };
    }

    const mappingResult = await this.ensureSensorMapping(
      sensorId,
      plotId,
      sensorType
    );

    return {
      plotId: mappingResult.plotId,
      sensorId,
      sensorType,
      wasCreated: mappingResult.wasCreated,
      previousPlotId: mappingResult.previousPlotId
    };
  }
}

module.exports = GeoSpatialSensorResolver;
