import type { SensorDataPoint } from '../types/moisture-chart.types';

type Mode = 'raw' | 'smoothed' | 'both';

type Thresholds = {
  lower: number | null | undefined;
  upper: number | null | undefined;
};

type XY = { x: Date; y: number | null };

export const defaultPalette = {
  surface: 'rgb(20, 184, 166)',        // teal (raw)
  deep: 'rgb(236, 72, 153)',           // pink (raw)
  surfaceSmoothed: 'rgb(2, 132, 199)', // blue (smoothed)
  deepSmoothed: 'rgb(139, 92, 246)',   // violet (smoothed)
  lower: 'rgb(220, 38, 38)',           // red
  upper: 'rgb(234, 179, 8)',           // amber
} as const;

export function buildLineDataset(
  label: string,
  data: XY[],
  color: string,
  opts: Partial<{ order: number; borderDash: number[]; borderWidth: number; tension: number; pointRadius: number; fill: boolean; spanGaps: boolean }>
) {
  return {
    label,
    data,
    borderColor: color,
    backgroundColor: 'rgba(0,0,0,0)',
    borderWidth: 2,
    tension: 0.4,
    fill: false,
    spanGaps: true,
    pointRadius: 2,
    pointHoverRadius: 4,
    ...opts,
  } as const;
}

function toXY(series: SensorDataPoint[], pick: (p: SensorDataPoint) => number | null): XY[] {
  return series.map((p) => ({ x: new Date(p.time), y: pick(p) }));
}

function findRange(series: XY[]): { start: Date; end: Date } | null {
  if (!series.length) return null;
  return { start: series[0].x, end: series[series.length - 1].x };
}

export function computeSeriesDigest(input: { dataPoints?: { time: string | Date }[]; smoothedDataPoints?: { time: string | Date }[] }): string {
  const dp = input?.dataPoints || [];
  const sp = input?.smoothedDataPoints || [];
  const toISO = (t: any) => (t instanceof Date ? t.toISOString() : new Date(t).toISOString());
  const a = dp.length ? `${toISO(dp[0].time)}|${toISO(dp[dp.length - 1].time)}` : 'none|none';
  const b = sp.length ? `${toISO(sp[0].time)}|${toISO(sp[sp.length - 1].time)}` : 'none|none';
  return `${dp.length}:${a}__${sp.length}:${b}`;
}

export function assembleMoistureDatasets(
  mode: Mode,
  dataPoints: SensorDataPoint[],
  smoothedDataPoints: SensorDataPoint[] | undefined,
  thresholds: Thresholds | undefined,
  palette = defaultPalette
) {
  const rawSurface = toXY(dataPoints, (p) => p.avgMoistureSurface);
  const rawDeep = toXY(dataPoints, (p) => p.avgMoistureDeep);
  const smoothSurface = toXY(smoothedDataPoints || [], (p) => p.avgMoistureSurface);
  const smoothDeep = toXY(smoothedDataPoints || [], (p) => p.avgMoistureDeep);

  // Range selection: selected series or union for BOTH
  let range: { start: Date; end: Date } | null = null;
  if (mode === 'both') {
    const candidates: Date[] = [];
    const pushRange = (s: XY[]) => { if (s.length) { candidates.push(s[0].x, s[s.length-1].x); } };
    pushRange(rawSurface.length ? rawSurface : rawDeep);
    pushRange(smoothSurface.length ? smoothSurface : smoothDeep);
    if (candidates.length) {
      range = { start: new Date(Math.min(...candidates.map(d=>d.getTime()))), end: new Date(Math.max(...candidates.map(d=>d.getTime()))) };
    }
  } else {
    const src = mode === 'smoothed' ? (smoothSurface.length ? smoothSurface : smoothDeep) : (rawSurface.length ? rawSurface : rawDeep);
    range = findRange(src);
  }

  const datasets: any[] = [];

  if (mode === 'raw') {
    datasets.push(buildLineDataset('Surface', rawSurface, palette.surface, { order: 1 }));
    datasets.push(buildLineDataset('Deep', rawDeep, palette.deep, { order: 2, borderDash: [5, 5] }));
  } else if (mode === 'smoothed') {
    datasets.push(buildLineDataset('Smoothed surface', smoothSurface, palette.surfaceSmoothed, { order: 1, borderWidth: 3 }));
    datasets.push(buildLineDataset('Smoothed deep', smoothDeep, palette.deepSmoothed, { order: 2, borderDash: [6, 4], borderWidth: 3 }));
  } else {
    // both
    datasets.push(buildLineDataset('Surface', rawSurface, palette.surface, { order: 1 }));
    datasets.push(buildLineDataset('Deep', rawDeep, palette.deep, { order: 2, borderDash: [5, 5] }));
  }

  if (thresholds && range) {
    const { start, end } = range;
    if (thresholds.lower !== null && thresholds.lower !== undefined) {
      datasets.push(
        buildLineDataset('Lower threshold', [{ x: start, y: thresholds.lower }, { x: end, y: thresholds.lower }], palette.lower, { order: 3, borderWidth: 1, tension: 0, pointRadius: 0 })
      );
    }
    if (thresholds.upper !== null && thresholds.upper !== undefined) {
      datasets.push(
        buildLineDataset('Upper threshold', [{ x: start, y: thresholds.upper }, { x: end, y: thresholds.upper }], palette.upper, { order: 4, borderWidth: 1, tension: 0, pointRadius: 0 })
      );
    }
  }

  if (mode === 'both') {
    datasets.push(buildLineDataset('Smoothed surface', smoothSurface, palette.surfaceSmoothed, { order: 5, borderWidth: 3 }));
    datasets.push(buildLineDataset('Smoothed deep', smoothDeep, palette.deepSmoothed, { order: 6, borderDash: [6, 4], borderWidth: 3 }));
  }

  return datasets;
}
