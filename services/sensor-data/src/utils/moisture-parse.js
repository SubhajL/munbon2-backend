/*
  Shared moisture parsing utilities.
  - parseNumeric preserves 0; null for blanks/non-numeric/out-of-range
  - sanitizeMoistureSensor maps incoming raw sensor fields to sanitized values
  - parseBody parses text/plain JSON or returns object as-is
  - buildMoistureInsert prepares value array for INSERT into moisture_readings
*/

'use strict';

function parseNumeric(value, min, max) {
  if (value === null || value === undefined || value === '') return null;
  const n = typeof value === 'number' ? value : parseFloat(value);
  if (Number.isNaN(n)) return null;
  if (min != null && n < min) return null;
  if (max != null && n > max) return null;
  return n; // keep 0
}

function toVoltage(battRaw) {
  const n = parseNumeric(battRaw, null, null);
  if (n === null) return null;
  const v = n / 100;
  // Cap to 9.99 similar to existing path to fit NUMERIC(3,2)
  return Math.min(v, 9.99);
}

function clampNumeric(value, min, max) {
  if (value === null || value === undefined || value === '') return null;
  const n = typeof value === 'number' ? value : parseFloat(value);
  if (Number.isNaN(n)) return null;
  return Math.max(min, Math.min(max, n));
}

function sanitizeMoistureSensor(sensor) {
  // Clamp moisture-related percentages to [0,100]
  const moistureSurfacePct = clampNumeric(sensor?.humid_hi, 0, 100);
  const moistureDeepPct = clampNumeric(sensor?.humid_low, 0, 100);
  // Temperatures remain validated (null if out-of-range)
  const tempSurfaceC = parseNumeric(sensor?.temp_hi, -50, 100);
  const tempDeepC = parseNumeric(sensor?.temp_low, -50, 100);
  // Ambient humidity also clamped to [0,100] per policy
  const ambientHumidityPct = clampNumeric(sensor?.amb_humid, 0, 100);
  const ambientTempC = parseNumeric(sensor?.amb_temp, -50, 100);
  const voltage = toVoltage(sensor?.sensor_batt);
  const floodStatus = sensor?.flood === 'yes';

  return {
    moistureSurfacePct,
    moistureDeepPct,
    tempSurfaceC,
    tempDeepC,
    ambientHumidityPct,
    ambientTempC,
    voltage,
    floodStatus,
  };
}

function parseBody(contentType, rawBody) {
  const ct = (contentType || '').toLowerCase();
  if (ct.includes('text/plain')) {
    if (typeof rawBody !== 'string') return rawBody; // assume already parsed upstream
    try {
      return JSON.parse(rawBody);
    } catch (err) {
      const e = new Error(`Invalid JSON in text/plain body: ${err.message}`);
      e.cause = err;
      throw e;
    }
  }
  // application/json or already object
  return rawBody;
}

function formatMoistureSensorId(gatewayId, sensorId) {
  const gw = String(gatewayId || '').padStart(4, '0');
  const sn = String(sensorId || '').padStart(4, '0');
  return `${gw}-${sn}`;
}

function buildMoistureInsert(gatewayId, rawSensor, location, timestamp) {
  const s = sanitizeMoistureSensor(rawSensor);
  const sensorId = formatMoistureSensorId(gatewayId, rawSensor?.sensor_id);
  const lat = parseNumeric(location?.lat, -90, 90);
  const lng = parseNumeric(location?.lng, -180, 180);
  const ts = timestamp instanceof Date ? timestamp : new Date(timestamp || Date.now());
  return {
    sensorId,
    values: [
      ts,
      sensorId,
      lat ?? null,
      lng ?? null,
      s.moistureSurfacePct,
      s.moistureDeepPct,
      s.tempSurfaceC,
      s.tempDeepC,
      s.ambientHumidityPct,
      s.ambientTempC,
      s.voltage,
      s.floodStatus,
      0.95,
    ],
  };
}

module.exports = {
  parseNumeric,
  sanitizeMoistureSensor,
  parseBody,
  buildMoistureInsert,
  formatMoistureSensorId,
  toVoltage,
  clampNumeric,
};
