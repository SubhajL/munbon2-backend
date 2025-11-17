const { SCADA_NAME_MAP } = require('../lib/resolvePlotValveMap');

function toScada(valve) {
  return SCADA_NAME_MAP.get(valve) || null;
}

function filterByPlots(rows, pattern) {
  if (!pattern) return rows;
  const parts = pattern.split(',').map((s) => s.trim());
  const test = (key) => parts.some((pat) => (pat.endsWith('*') ? key.startsWith(pat.slice(0, -1)) : key === pat));
  return rows.filter((r) => test(r.plotId));
}

async function fetchValveMapAndFormat({ repo, json = false, onlyScada = false, plotsPattern = null }) {
  const rows = await repo.getAllValvePlotMappings(); // [{plotId,valveName}]
  const enriched = rows
    .filter((r) => /^SF-/.test(r.plotId))
    .map((r) => ({ plotId: r.plotId, valveId: r.valveName, scadaValve: r.valveName ? toScada(r.valveName) : null }))
    .sort((a, b) => (a.plotId < b.plotId ? -1 : a.plotId > b.plotId ? 1 : 0));

  const filtered = filterByPlots(enriched, plotsPattern);

  if (json) {
    return JSON.stringify(
      onlyScada ? filtered.map((r) => ({ plotId: r.plotId, scadaValve: r.scadaValve })) : filtered,
      null,
      2
    );
  }

  const header = onlyScada ? ['Plot', 'SCADA Valve'] : ['Plot', 'SmartFarm Valve', 'SCADA Valve'];
  const grid = [header].concat(
    filtered.map((r) => (onlyScada ? [r.plotId, r.scadaValve || '-'] : [r.plotId, r.valveId || '-', r.scadaValve || '-']))
  );
  const widths = header.map((_, i) => Math.max(...grid.map((row) => String(row[i]).length)));
  const line = (cols) => cols.map((c, i) => String(c).padEnd(widths[i])).join('  ');
  const lines = grid.map((r, idx) => (idx === 1 ? [line(r), widths.map((w) => '-'.repeat(w)).join('  ')].join('\n') : line(r)));
  return lines.join('\n');
}

module.exports = { fetchValveMapAndFormat };