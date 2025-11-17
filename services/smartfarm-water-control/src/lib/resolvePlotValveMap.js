'use strict';
const fs = require('fs');
const path = require('path');

// SCADA name mapping copied from ValveCommandService (kept in sync)
const SCADA_NAME_MAP = new Map([
  ['SV-U1', 'SV_C1_L'],
  ['SV-U2', 'SV_C1_R'],
  ['SV-U3', 'SV_C2_L'],
  ['SV-U4', 'SV_C2_R'],
  ['SV-U5', 'SV_C3_L'],
  ['SV-U6', 'SV_C3_R'],
  ['SV-U7', 'SV_C4_L'],
  ['SV-U8', 'SV_C4_R'],
  ['SV-L1', 'SV_L'],
  ['SV-L5', 'SV_M'],
  ['SV-L2', 'SV_N'],
  ['SV-L3', 'SV_O'],
  ['SV-L6', 'SV_P'],
  ['SV-L4', 'SV_Q']
]);

function toScadaValveName(valveId) {
  return SCADA_NAME_MAP.get(valveId) || null;
}

function loadDeviceMapping(filePath) {
  const abs = path.isAbsolute(filePath)
    ? filePath
    : path.resolve(process.cwd(), filePath);
  const raw = fs.readFileSync(abs, 'utf8');
  return JSON.parse(raw);
}

function resolvePlotToValveMap(opts = {}) {
  const {
    mappingJson,
    deviceMappingPath = path.resolve(__dirname, '../../config/device-mapping.json'),
    includeUUIDs = false,
    onlySF = true
  } = opts;

  const mapping = mappingJson || loadDeviceMapping(deviceMappingPath);
  const out = [];

  const entries = mapping && mapping.plot_device_mapping ? mapping.plot_device_mapping : {};
  for (const [plotKey, cfg] of Object.entries(entries)) {
    const isSF = /^SF-/.test(plotKey);
    if (onlySF && !isSF) continue;
    if (!includeUUIDs && !isSF) continue;

    const valveId = cfg && cfg.devices ? cfg.devices.solenoid_valve || null : null;
    out.push({
      plotKey,
      valveId,
      scadaValve: valveId ? toScadaValveName(valveId) : null
    });
  }

  // Sort by plotKey for stable output
  out.sort((a, b) => (a.plotKey < b.plotKey ? -1 : a.plotKey > b.plotKey ? 1 : 0));
  return out;
}

module.exports = {
  resolvePlotToValveMap,
  toScadaValveName,
  loadDeviceMapping,
  SCADA_NAME_MAP
};