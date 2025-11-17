class ShapeIngestService {
  constructor({ repo, logger }) {
    this.repo = repo;
    this.logger = logger || console;
  }

  parseGeoJSON(geojson) {
    const proj4 = require('proj4');
    // Define UTM Zone 48N if needed
    if (!proj4.defs['EPSG:32648']) {
      proj4.defs('EPSG:32648', '+proj=utm +zone=48 +datum=WGS84 +units=m +no_defs +type=crs');
    }
    if (!geojson || geojson.type !== 'FeatureCollection') {
      throw new Error('Invalid GeoJSON FeatureCollection');
    }
    const results = [];
    for (const f of geojson.features || []) {
      const props = f.properties || {};
      const geom = f.geometry;
      if (!geom || geom.type !== 'Polygon') {
        throw new Error('Geometry must be Polygon');
      }
      // Accept new schema: use plot_id if present; else derive from name/crop_id
      let plotId = props.plot_id || props.plotId || props.name || props.crop_id;
      if (!plotId) throw new Error('plot_id missing');
      // Normalize to SF-* string
      if (!/^SF-/.test(plotId)) plotId = `SF-${plotId}`;
      if (!plotId) throw new Error('plot_id missing');
      const areaRai = Number(props.area_rai ?? props.areaRai ?? 0);
      if (!(areaRai > 0)) throw new Error('area_rai must be > 0');
      // Reproject to WGS84 if coords look like UTM meters
      let geometry = geom;
      const first = geom.coordinates?.[0]?.[0];
      if (Array.isArray(first) && first[0] > 1000 && first[1] > 1000) {
        const toLonLatRing = ring => ring.map(([x, y]) => proj4('EPSG:32648', 'WGS84', [x, y]));
        const reprojected = geom.coordinates.map(ring => toLonLatRing(ring));
        geometry = { type: 'Polygon', coordinates: reprojected };
      }

      results.push({
        plotId,
        plotName: props.plot_name || props.plotName || props.name || null,
        areaRai,
        geojson: geometry
      });
    }
    return results;
  }

  parseDeviceMapping(mappingJson) {
    if (!mappingJson || typeof mappingJson !== 'object') throw new Error('Invalid mapping');
    const devices = { solenoid_valves: [], flow_meters: [], moisture_sensors: [] };

    for (const sv of mappingJson.devices?.solenoid_valves || []) {
      devices.solenoid_valves.push({
        deviceName: sv.device_name,
        deviceType: 'solenoid_valve',
        lng: sv.coordinates?.[0],
        lat: sv.coordinates?.[1],
        zone: sv.zone || null,
        metadata: { control_mode: sv.control_mode || null }
      });
    }
    for (const fm of mappingJson.devices?.flow_meters || []) {
      devices.flow_meters.push({
        deviceName: fm.device_name,
        deviceType: 'flow_meter',
        lng: fm.coordinates?.[0],
        lat: fm.coordinates?.[1],
        zone: fm.zone || null,
        metadata: { monitors: fm.monitors || [] }
      });
    }
    for (const ms of mappingJson.devices?.moisture_sensors || []) {
      devices.moisture_sensors.push({
        deviceId: ms.device_id,
        deviceName: ms.device_name,
        deviceType: 'moisture_sensor',
        lng: ms.coordinates?.[0],
        lat: ms.coordinates?.[1],
        position: ms.position || null
      });
    }

    // Per-plot assignments
    const assignments = new Map();
    const mapping = mappingJson.plot_device_mapping || {};
    for (const [plotId, entry] of Object.entries(mapping)) {
      assignments.set(plotId, {
        valveId: entry.devices?.solenoid_valve || null,
        flowmeterId: entry.devices?.flow_meter || null,
        sensorId: entry.devices?.moisture_sensor || null,
        controlMode: entry.control_mode || null,
        areaRai: entry.area_rai || null,
        plotName: entry.plot_name || null
      });
    }

    return { devices, assignments };
  }

  planChanges({ plots, devices, assignments }) {
    // Prepare ordered batches for upsert
    const plotBoundaries = plots.map(p => ({ plotId: p.plotId, plotName: p.plotName, areaRai: p.areaRai, geojson: p.geojson }));

    const flattenedDevices = [];
    for (const sv of devices.solenoid_valves) flattenedDevices.push({ ...sv });
    for (const fm of devices.flow_meters) flattenedDevices.push({ ...fm });

    // Sensors for sensor_locations
    const sensors = devices.moisture_sensors.map(ms => ({
      deviceId: ms.deviceId,
      deviceName: ms.deviceName,
      deviceType: 'moisture_sensor',
      lng: ms.lng,
      lat: ms.lat,
      plotId: null
    }));

    // Plot configurations and sensor mappings
    const plotConfigs = [];
    const sensorMappings = [];
    for (const p of plots) {
      const a = assignments.get(p.plotId) || {};
      plotConfigs.push({
        plotId: p.plotId,
        cropType: a.cropType || 'rice',
        controlMode: a.controlMode || 'MOISTURE',
        valveId: a.valveId || null,
        flowmeterId: a.flowmeterId || null,
        areaRai: a.areaRai || p.areaRai
      });
      if (a.sensorId) {
        sensorMappings.push({ sensorId: a.sensorId, plotId: p.plotId, sensorType: 'moisture' });
        // also link sensor location to plot if present in sensors list
        const s = sensors.find(x => x.deviceName === a.sensorId || x.deviceId === a.sensorId);
        if (s) s.plotId = p.plotId;
      }
    }

    return { plotBoundaries, devices: flattenedDevices, sensors, plotConfigs, sensorMappings };
  }

  async applyUpserts(plan) {
    const counts = { plotBoundaries: 0, devices: 0, sensors: 0, plotConfigs: 0, sensorMappings: 0 };

    for (const pb of plan.plotBoundaries) { await this.repo.upsertPlotBoundary(pb); counts.plotBoundaries++; }
    for (const d of plan.devices) { await this.repo.upsertDevice(d); counts.devices++; }
    for (const s of plan.sensors) { await this.repo.upsertSensorLocation(s); counts.sensors++; }
    for (const pc of plan.plotConfigs) { await this.repo.upsertPlotConfiguration(pc); counts.plotConfigs++; }
    for (const sm of plan.sensorMappings) { await this.repo.upsertSensorMapping(sm); counts.sensorMappings++; }

    return counts;
  }
}

module.exports = ShapeIngestService;