const fs = require("fs");
const path = require("path");

/**
 * Load smart farm plots from GeoJSON file
 * @param {string} geoJsonPath - Absolute path to GeoJSON file
 * @returns {Array} Array of plot objects with id, areaRai, geometry
 */
function loadSmartFarmPlots(geoJsonPath) {
  if (!fs.existsSync(geoJsonPath)) {
    throw new Error(`GeoJSON file not found: ${geoJsonPath}`);
  }

  let geoJson;
  try {
    const content = fs.readFileSync(geoJsonPath, "utf8");
    geoJson = JSON.parse(content);
  } catch (error) {
    throw new Error(`Failed to parse GeoJSON file: ${error.message}`);
  }

  if (!geoJson.features || !Array.isArray(geoJson.features)) {
    throw new Error("Invalid GeoJSON: missing features array");
  }

  return geoJson.features.map((feature) => {
    if (!feature.properties || !feature.properties.crop_id) {
      throw new Error("GeoJSON feature missing crop_id property");
    }

    if (!feature.properties.area_rai) {
      throw new Error("GeoJSON feature missing area_rai property");
    }

    if (!feature.geometry) {
      throw new Error("GeoJSON feature missing geometry");
    }

    return {
      id: feature.properties.crop_id,
      areaRai: feature.properties.area_rai,
      geometry: feature.geometry,
    };
  });
}

/**
 * Merge plot features from GeoJSON with environment configuration
 * @param {Array} plotFeatures - Array of plot objects from GeoJSON
 * @param {Object} envConfig - Map of plot IDs to sensor/valve config
 * @returns {Array} Merged plot configurations
 */
function mergePlotConfig(plotFeatures, envConfig) {
  // Filter to only plots that have env configuration
  const configuredPlotIds = Object.keys(envConfig);
  const filteredPlots = plotFeatures.filter((plot) =>
    configuredPlotIds.includes(plot.id),
  );

  // Verify all configured plots exist in GeoJSON
  configuredPlotIds.forEach((plotId) => {
    const plotExists = plotFeatures.some((plot) => plot.id === plotId);
    if (!plotExists) {
      throw new Error(
        `Plot ${plotId} configured in env but not found in GeoJSON`,
      );
    }
  });

  return filteredPlots.map((plot) => {
    const config = envConfig[plot.id];

    return {
      plotId: plot.id,
      areaRai: plot.areaRai,
      sensorId: config.sensorId,
      valveName: config.valveName,
      cropType: config.cropType || "rice",
      geometry: plot.geometry,
    };
  });
}

/**
 * Validate plot mappings have all required fields
 * @param {Array} plots - Array of plot configurations
 * @throws {Error} If validation fails
 */
function validatePlotMappings(plots) {
  const requiredFields = ["plotId", "sensorId", "valveName", "areaRai"];

  plots.forEach((plot) => {
    requiredFields.forEach((field) => {
      if (!plot[field]) {
        throw new Error(
          `Plot ${plot.plotId || "unknown"} missing required field: ${field}`,
        );
      }
    });
  });
}

module.exports = {
  loadSmartFarmPlots,
  mergePlotConfig,
  validatePlotMappings,
};
