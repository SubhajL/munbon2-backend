/**
 * Pure functions for threshold validation
 */

/**
 * Validate threshold range values
 * @param {{moistureLower: number, moistureUpper: number, waterLevelLower: number, waterLevelUpper: number}} threshold
 * @returns {Array<string>} Array of validation errors (empty if valid)
 */
function validateThresholdRange(threshold) {
  const errors = [];

  const moistureValidation = validateMoistureThreshold(
    threshold.moistureLower,
    threshold.moistureUpper
  );
  if (!moistureValidation.valid) {
    errors.push(...moistureValidation.errors);
  }

  const waterLevelValidation = validateWaterLevelThreshold(
    threshold.waterLevelLower,
    threshold.waterLevelUpper
  );
  if (!waterLevelValidation.valid) {
    errors.push(...waterLevelValidation.errors);
  }

  return errors;
}

/**
 * Find plots that exist in one set but not the other
 * @param {Array<string>} geoJsonPlotIds - Plot IDs from GeoJSON
 * @param {Array<string>} dbPlotIds - Plot IDs from database
 * @returns {{missingInDb: Array<string>, missingInGeoJSON: Array<string>}}
 */
function findMissingPlots(geoJsonPlotIds, dbPlotIds) {
  const geoJsonSet = new Set(geoJsonPlotIds);
  const dbSet = new Set(dbPlotIds);

  const missingInDb = geoJsonPlotIds.filter((id) => !dbSet.has(id));
  const missingInGeoJSON = dbPlotIds.filter((id) => !geoJsonSet.has(id));

  return { missingInDb, missingInGeoJSON };
}

/**
 * Separate test plots from real plots
 * @param {Array<string>} plotIds - All plot IDs
 * @param {string} testPlotPrefix - Prefix for test plots (default "TEST-PLOT-")
 * @returns {{realPlots: Array<string>, testPlots: Array<string>}}
 */
function separateTestPlots(plotIds, testPlotPrefix = 'TEST-PLOT-') {
  const realPlots = plotIds.filter((id) => !id.startsWith(testPlotPrefix));
  const testPlots = plotIds.filter((id) => id.startsWith(testPlotPrefix));

  return { realPlots, testPlots };
}

/**
 * Validate moisture threshold bounds
 * @param {number} lower - Lower bound
 * @param {number} upper - Upper bound
 * @returns {{valid: boolean, errors: Array<string>}}
 */
function validateMoistureThreshold(lower, upper) {
  const errors = [];

  if (lower < 0 || lower > 100) {
    errors.push(`moisture_lower_threshold ${lower} outside range [0,100]`);
  }

  if (upper < 0 || upper > 100) {
    errors.push(`moisture_upper_threshold ${upper} outside range [0,100]`);
  }

  if (lower >= upper) {
    errors.push(
      `moisture_lower_threshold ${lower} >= moisture_upper_threshold ${upper}`
    );
  }

  return { valid: errors.length === 0, errors };
}

/**
 * Validate water level threshold bounds
 * @param {number} lower - Lower bound
 * @param {number} upper - Upper bound
 * @returns {{valid: boolean, errors: Array<string>}}
 */
function validateWaterLevelThreshold(lower, upper) {
  const errors = [];

  if (lower >= upper) {
    errors.push(
      `water_level_lower_threshold ${lower} >= water_level_upper_threshold ${upper}`
    );
  }

  return { valid: errors.length === 0, errors };
}

module.exports = {
  validateThresholdRange,
  findMissingPlots,
  separateTestPlots,
  validateMoistureThreshold,
  validateWaterLevelThreshold
};
