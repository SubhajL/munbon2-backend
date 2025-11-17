/**
 * Pure functions for moisture data analysis
 */

/**
 * Aggregate moisture readings by plot ID
 * @param {Array<{plot_id: string, moisture_surface_pct: number}>} readings
 * @returns {Map<string, {min: number, max: number, mean: number, median: number, stddev: number, count: number}>}
 */
function aggregateMoistureByPlot(readings) {
  const grouped = new Map();

  readings.forEach((reading) => {
    const plotId = reading.plot_id;
    if (!grouped.has(plotId)) {
      grouped.set(plotId, []);
    }
    const value = Number(reading.moisture_surface_pct);
    grouped.get(plotId).push(value);
  });

  const result = new Map();
  grouped.forEach((values, plotId) => {
    result.set(plotId, calculateMoistureStats(values));
  });

  return result;
}

/**
 * Calculate statistical measures for moisture values
 * @param {Array<number>} values
 * @returns {{min: number, max: number, mean: number, median: number, stddev: number, count: number}}
 */
function calculateMoistureStats(values) {
  const validValues = values
    .map((v) => Number(v))
    .filter((v) => !isNaN(v) && isFinite(v));

  if (validValues.length === 0) {
    return { min: 0, max: 0, mean: 0, median: 0, stddev: 0, count: 0 };
  }

  const sorted = [...validValues].sort((a, b) => a - b);
  const count = validValues.length;
  const min = sorted[0];
  const max = sorted[count - 1];

  const sum = validValues.reduce((acc, val) => acc + val, 0);
  const mean = sum / count;

  const median =
    count % 2 === 0
      ? (sorted[count / 2 - 1] + sorted[count / 2]) / 2
      : sorted[Math.floor(count / 2)];

  const squaredDiffs = validValues.map((val) => Math.pow(val - mean, 2));
  const variance = squaredDiffs.reduce((acc, val) => acc + val, 0) / count;
  const stddev = Math.sqrt(variance);

  return { min, max, mean, median, stddev, count };
}

/**
 * Identify outlier readings (>2 standard deviations from mean)
 * @param {Array<{plot_id: string, moisture_surface_pct: number, time: string}>} readings
 * @param {{mean: number, stddev: number}} stats
 * @returns {Array<{plot_id: string, moisture_surface_pct: number, time: string}>}
 */
function identifyOutliers(readings, stats) {
  if (stats.stddev === 0) {
    return [];
  }

  const threshold = 2 * stats.stddev;
  return readings.filter((reading) => {
    const value = Number(reading.moisture_surface_pct);
    const deviation = Math.abs(value - stats.mean);
    return deviation > threshold;
  });
}

module.exports = {
  aggregateMoistureByPlot,
  calculateMoistureStats,
  identifyOutliers
};
