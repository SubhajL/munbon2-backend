/**
 * Pure functions for threshold comparison and analysis
 */

/**
 * Calculate percentage of readings outside threshold range
 * @param {Array<number>} readings - Moisture readings
 * @param {number} lowerThreshold - Lower bound
 * @param {number} upperThreshold - Upper bound
 * @returns {{percentage: number, belowCount: number, aboveCount: number, totalCount: number}}
 */
function calculateOutOfRangePercentage(
  readings,
  lowerThreshold,
  upperThreshold
) {
  if (readings.length === 0) {
    return { percentage: 0, belowCount: 0, aboveCount: 0, totalCount: 0 };
  }

  const numericReadings = readings.map((r) => Number(r));
  const belowCount = numericReadings.filter((r) => r < lowerThreshold).length;
  const aboveCount = numericReadings.filter((r) => r > upperThreshold).length;
  const totalCount = numericReadings.length;
  const outOfRangeCount = belowCount + aboveCount;
  const percentage = (outOfRangeCount / totalCount) * 100;

  return { percentage, belowCount, aboveCount, totalCount };
}

/**
 * Compare threshold configuration to historical data
 * @param {{moistureLower: number, moistureUpper: number}} threshold
 * @param {{min: number, max: number, mean: number, outOfRangePercent: number}} historicalStats
 * @returns {{needsAdjustment: boolean, outOfRangePercent: number, recommendation: string}}
 */
function compareThresholdToData(threshold, historicalStats) {
  const needsAdjustment = historicalStats.outOfRangePercent > 30;

  const recommendation = needsAdjustment
    ? `${historicalStats.outOfRangePercent.toFixed(1)}% of readings fall outside current thresholds. Consider adjustment.`
    : `Thresholds are appropriate. ${historicalStats.outOfRangePercent.toFixed(1)}% out of range.`;

  return {
    needsAdjustment,
    outOfRangePercent: historicalStats.outOfRangePercent,
    recommendation
  };
}

/**
 * Generate recommended threshold values based on historical data
 * @param {{moistureLower: number, moistureUpper: number}} currentThreshold
 * @param {{mean: number, stddev: number, min: number, max: number}} historicalStats
 * @returns {{moistureLower: number, moistureUpper: number, reasoning: string}}
 */
function generateThresholdRecommendation(currentThreshold, historicalStats) {
  const buffer = Math.max(historicalStats.stddev * 1.5, 10);

  let moistureLower = Math.max(0, historicalStats.mean - buffer);
  let moistureUpper = Math.min(100, historicalStats.mean + buffer);

  moistureLower = Math.max(0, Math.min(moistureLower, 90));
  moistureUpper = Math.max(10, Math.min(100, moistureUpper));

  if (moistureLower >= moistureUpper) {
    moistureLower = Math.max(0, moistureUpper - 10);
  }

  const reasoning = `Based on mean ${historicalStats.mean.toFixed(1)}% and stddev ${historicalStats.stddev.toFixed(1)}%, recommend bounds centered around mean with 1.5x stddev buffer.`;

  return { moistureLower, moistureUpper, reasoning };
}

/**
 * Categorize threshold status based on out-of-range percentage
 * @param {number} outOfRangePercent - Percentage of readings out of range
 * @returns {"GOOD"|"ACCEPTABLE"|"NEEDS_ADJUSTMENT"}
 */
function categorizeThresholdStatus(outOfRangePercent) {
  if (outOfRangePercent < 10) {
    return 'GOOD';
  }
  if (outOfRangePercent <= 30) {
    return 'ACCEPTABLE';
  }
  return 'NEEDS_ADJUSTMENT';
}

module.exports = {
  calculateOutOfRangePercentage,
  compareThresholdToData,
  generateThresholdRecommendation,
  categorizeThresholdStatus
};
