const fs = require('fs');
const path = require('path');

function parseMappingFile(filePath) {
  const abs = path.isAbsolute(filePath) ? filePath : path.resolve(process.cwd(), filePath);
  const raw = fs.readFileSync(abs, 'utf8');
  const json = JSON.parse(raw);
  const entries = json?.plot_device_mapping || {};
  const pairs = [];
  for (const [plotId, cfg] of Object.entries(entries)) {
    if (!/^SF-/.test(plotId)) continue; // only SF-* plots
    const valve = cfg?.devices?.solenoid_valve || null;
    if (!valve) continue;
    pairs.push({ plotId, valveName: valve });
  }
  return pairs;
}

async function seedValveMapFromJson({ filePath, repo, updatedBy = 'seed' }) {
  const pairs = parseMappingFile(filePath);
  let created = 0;
  const seenValves = new Set();
  for (const p of pairs) {
    if (seenValves.has(p.valveName)) continue; // avoid unique(smartfarm_valve_name) violation
    await repo.upsertValvePlotMapping({ plotId: p.plotId, valveName: p.valveName, updatedBy });
    seenValves.add(p.valveName);
    created += 1;
  }
  return { created };
}

module.exports = { seedValveMapFromJson, parseMappingFile };