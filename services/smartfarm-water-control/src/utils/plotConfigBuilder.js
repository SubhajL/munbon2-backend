function buildPlotConfigsFromEnriched({ plots, mappings, deviceOverrides }) {
  const byPlot = new Map();
  const plotIds = [];

  // Initialize plot entries from enriched plots view
  for (const row of plots) {
    const plotId = row.plot_id;
    plotIds.push(plotId);
    byPlot.set(plotId, {
      plotId,
      cropType: row.crop_type,
      controlMode: row.control_mode,
      areaRai: Number(row.area_rai) || 0,
      moistureSensorId: null,
      waterLevelSensorId: null,
      valveId: row.valve_id || row.solenoid_valve || null
    });
  }

  // Attach sensor mappings
  for (const m of mappings) {
    const plot = byPlot.get(m.plot_id);
    if (!plot) continue;
    if (m.sensor_type === 'moisture') plot.moistureSensorId = m.sensor_id;
    if (m.sensor_type === 'water_level') plot.waterLevelSensorId = m.sensor_id;
  }

  // Apply overrides if provided
  if (deviceOverrides && deviceOverrides.byPlotId instanceof Map) {
    for (const [plotId, override] of deviceOverrides.byPlotId.entries()) {
      const plot = byPlot.get(plotId);
      if (!plot) continue;
      if (override.solenoidValve) plot.valveId = override.solenoidValve;
    }
  }

  // Ensure valve ids defaulted; set primary sensor by control mode
  const plotsOut = [];
  const valveMapping = new Map();
  for (const plot of byPlot.values()) {
    if (!plot.valveId) {
      const shortId = String(plot.plotId).substring(0, 8);
      plot.valveId = `SV_${shortId}`;
    }
    plot.sensorId = plot.controlMode === 'MOISTURE' ? plot.moistureSensorId : plot.waterLevelSensorId;
    plot.valveName = plot.valveId;
    plotsOut.push(plot);
    valveMapping.set(plot.plotId, plot.valveId);
  }

  return { plots: plotsOut, valveMapping };
}

module.exports = { buildPlotConfigsFromEnriched };