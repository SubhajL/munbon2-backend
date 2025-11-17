'use strict';

/**
 * Split a cropType string into ordered, unique tokens suitable for lookup.
 * - Splits on whitespace
 * - Trims tokens
 * - Filters empties
 * - Deduplicates while preserving order
 */
function tokenizeCropType(cropType) {
  if (!cropType || typeof cropType !== 'string') return [];
  const raw = cropType
    .split(/\s+/)
    .map((t) => t.trim())
    .filter((t) => t.length > 0);

  const seen = new Set();
  const tokens = [];
  for (const t of raw) {
    if (!seen.has(t)) {
      seen.add(t);
      tokens.push(t);
    }
  }
  return tokens;
}

module.exports = { tokenizeCropType };