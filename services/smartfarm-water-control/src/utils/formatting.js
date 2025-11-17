/**
 * Pure formatting utilities
 */

/**
 * Format data as ASCII table
 * @param {Array<string>} headers - Column headers
 * @param {Array<Array<string>>} rows - Data rows
 * @param {Array<number>} columnWidths - Width for each column
 * @returns {string} Formatted ASCII table
 */
function formatAsciiTable(headers, rows, columnWidths) {
  const lines = [];

  const headerLine = headers
    .map((header, i) => header.padEnd(columnWidths[i]))
    .join('');
  lines.push(headerLine);

  const separator = columnWidths.map((width) => '-'.repeat(width)).join('');
  lines.push(separator);

  rows.forEach((row) => {
    const rowLine = row
      .map((cell, i) => String(cell).padEnd(columnWidths[i]))
      .join('');
    lines.push(rowLine);
  });

  return lines.join('\n');
}

/**
 * Format number as percentage
 * @param {number} value - Numeric value
 * @param {number} decimals - Decimal places (default 1)
 * @returns {string} Formatted percentage
 */
function formatPercentage(value, decimals = 1) {
  return `${value.toFixed(decimals)}%`;
}

/**
 * Format threshold change for display
 * @param {string} field - Field name
 * @param {number|null} currentValue - Current threshold value
 * @param {number} newValue - New threshold value
 * @returns {string} Formatted change string
 */
function formatThresholdChange(field, currentValue, newValue) {
  const fieldPadded = field.padEnd(25);
  const current = currentValue !== null ? String(currentValue) : 'NULL';
  const currentPadded = current.padEnd(12);
  return `${fieldPadded}${currentPadded}→  ${newValue}`;
}

/**
 * Shorten plot ID for display
 * @param {string} plotId - Full plot ID
 * @param {number} length - Max length (default 12)
 * @returns {string} Shortened ID
 */
function formatPlotIdShort(plotId, length = 12) {
  if (plotId.length <= length) {
    return plotId;
  }
  return plotId.substring(0, length) + '...';
}

/**
 * Format timestamp
 * @param {Date} date - Date object
 * @param {string} format - Format type: "ISO" or "LOCAL"
 * @returns {string} Formatted timestamp
 */
function formatTimestamp(date, format = 'ISO') {
  if (!(date instanceof Date) || isNaN(date.getTime())) {
    return 'Invalid Date';
  }

  if (format === 'LOCAL') {
    return date.toLocaleString();
  }

  return date.toISOString();
}

module.exports = {
  formatAsciiTable,
  formatPercentage,
  formatThresholdChange,
  formatPlotIdShort,
  formatTimestamp
};
