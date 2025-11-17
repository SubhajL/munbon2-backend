// Utility to load valve mapping from DB-only source (no JSON)
async function loadValveMappingFromDb(configRepository) {
  const rows = await configRepository.getAllValvePlotMappings();
  const map = new Map();
  for (const r of rows) map.set(r.plotId, r.valveName);
  return map;
}

module.exports = { loadValveMappingFromDb };