async function rebuildWlMappingFromGps({ tsRepo, cfgRepo, maxSensors = 1000, dryRun = false, logger = console } = {}) {
  const latest = await tsRepo.getLatestWLGpsPerSensor({ maxSensors });
  const updates = [];
  for (const row of latest) {
    const lat = Number(row.location_lat);
    const lng = Number(row.location_lng);
    if (!(Number.isFinite(lat) && Number.isFinite(lng))) continue;
    const plotId = await cfgRepo.findPlotByCoordinates(cfgRepo.pool, lng, lat);
    if (!plotId) continue;
    updates.push({ sensorId: row.sensor_id, plotId });
  }

  let upserts = 0;
  if (!dryRun) {
    for (const u of updates) {
      await cfgRepo.upsertWLSensorMapping({ sensorId: u.sensorId, plotId: u.plotId });
      upserts++;
    }
  }

  let deleted = 0;
  if (!dryRun) {
    deleted = await cfgRepo.deleteLegacyWLSfMappings();
  }

  const perPlot = updates.reduce((acc, u) => { acc[u.plotId] = (acc[u.plotId] || 0) + 1; return acc; }, {});
  const summary = { candidates: latest.length, mapped: updates.length, upserts, deletedLegacy: deleted, perPlot };
  logger.info(summary, 'WL remap summary');
  return summary;
}

module.exports = { rebuildWlMappingFromGps };