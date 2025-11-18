import { assembleMoistureDatasets, defaultPalette } from './chart-datasets';

const makePoint = (t: string, s: number | null, d: number | null) => ({
  time: t,
  avgMoistureSurface: s,
  minMoistureSurface: s,
  maxMoistureSurface: s,
  avgMoistureDeep: d,
  minMoistureDeep: d,
  maxMoistureDeep: d,
  sampleCount: 1,
});

  test('computeSeriesDigest_identical_series_same_digest', () => {
    const a = {
      dataPoints: [
        { time: '2025-11-03T12:00:00Z' },
        { time: '2025-11-03T12:15:00Z' },
      ] as any,
      smoothedDataPoints: [
        { time: '2025-11-03T12:00:00Z' },
        { time: '2025-11-03T12:15:00Z' },
      ] as any,
    };
    const b = JSON.parse(JSON.stringify(a));
    const { computeSeriesDigest } = require('./chart-datasets');
    expect(computeSeriesDigest(a)).toBe(computeSeriesDigest(b));
  });

  test('computeSeriesDigest_changes_on_new_point_or_time_shift', () => {
    const base = {
      dataPoints: [ { time: '2025-11-03T12:00:00Z' } ],
      smoothedDataPoints: [ { time: '2025-11-03T12:15:00Z' } ],
    } as any;
    const { computeSeriesDigest } = require('./chart-datasets');
    const d1 = computeSeriesDigest(base);
    const changed = {
      dataPoints: [ { time: '2025-11-03T12:00:00Z' }, { time: '2025-11-03T12:15:00Z' } ],
      smoothedDataPoints: [ { time: '2025-11-03T12:15:00Z' } ],
    } as any;
    const d2 = computeSeriesDigest(changed);
    expect(d1).not.toBe(d2);
  });


describe('assembleMoistureDatasets', () => {
  const dataPoints = [
    makePoint('2025-11-03T12:00:00Z', 60, 55),
    makePoint('2025-11-03T12:15:00Z', 62, 54),
  ];
  const smoothedDataPoints = [
    makePoint('2025-11-03T12:00:00Z', 59, 54),
    makePoint('2025-11-03T12:15:00Z', 60, 53),
  ];
  const thresholds = { lower: 50, upper: 70 } as const;

  test('assembleMoistureDatasets_RAW_returns_raw_series_only', () => {
    const ds = assembleMoistureDatasets('raw', dataPoints as any, smoothedDataPoints as any, thresholds, defaultPalette);
    const labels = ds.map((d) => d.label);
    expect(labels[0]).toBe('Surface');
    expect(labels[1]).toBe('Deep');
    expect(labels).not.toContain('Smoothed surface');
    expect(labels).not.toContain('Smoothed deep');
  });

  test('assembleMoistureDatasets_SMOOTHED_returns_smoothed_series_only', () => {
    const ds = assembleMoistureDatasets('smoothed', dataPoints as any, smoothedDataPoints as any, thresholds, defaultPalette);
    const labels = ds.map((d) => d.label);
    expect(labels[0]).toBe('Smoothed surface');
    expect(labels[1]).toBe('Smoothed deep');
    expect(labels).not.toContain('Surface');
    expect(labels).not.toContain('Deep');
  });

  test('assembleMoistureDatasets_BOTH_returns_all_four_series', () => {
    const ds = assembleMoistureDatasets('both', dataPoints as any, smoothedDataPoints as any, thresholds, defaultPalette);
    expect(ds.map(d=>d.label)).toEqual([
      'Surface','Deep','Lower threshold','Upper threshold','Smoothed surface','Smoothed deep'
    ]);
  });

  test('deep_series_is_dashed_in_both_modes', () => {
    const raw = assembleMoistureDatasets('raw', dataPoints as any, smoothedDataPoints as any, thresholds, defaultPalette);
    const smooth = assembleMoistureDatasets('smoothed', dataPoints as any, smoothedDataPoints as any, thresholds, defaultPalette);
    const both = assembleMoistureDatasets('both', dataPoints as any, smoothedDataPoints as any, thresholds, defaultPalette);
    expect(raw[1].borderDash).toEqual([5, 5]);
    expect(smooth[1].borderDash).toEqual([6, 4]);
    // in BOTH mode: raw deep at index 1, smoothed deep at last index
    expect(both[1].borderDash).toEqual([5, 5]);
    expect(both[both.length-1].borderDash).toEqual([6, 4]);
  });

  test('dataset_order_consistent_across_modes', () => {
    const raw = assembleMoistureDatasets('raw', dataPoints as any, smoothedDataPoints as any, thresholds, defaultPalette);
    const smooth = assembleMoistureDatasets('smoothed', dataPoints as any, smoothedDataPoints as any, thresholds, defaultPalette);
    const both = assembleMoistureDatasets('both', dataPoints as any, smoothedDataPoints as any, thresholds, defaultPalette);
    expect(raw.map((d) => d.order)).toEqual([1, 2, 3, 4]);
    expect(smooth.map((d) => d.order)).toEqual([1, 2, 3, 4]);
    expect(both.map((d) => d.order)).toEqual([1, 2, 3, 4, 5, 6]);
  });

  test('thresholds_span_selected_series_time_range', () => {
    const smooth = assembleMoistureDatasets('smoothed', dataPoints as any, smoothedDataPoints as any, thresholds, defaultPalette);
    const lower = smooth[2];
    const xs = (lower.data as any[]).map((p) => new Date(p.x).toISOString());
    expect(xs[0]).toBe('2025-11-03T12:00:00.000Z');
    expect(xs[1]).toBe('2025-11-03T12:15:00.000Z');
  });

  test('thresholds_span_union_range_in_both_mode', () => {
    const ds = assembleMoistureDatasets('both', [dataPoints[0]], [smoothedDataPoints[1]], thresholds, defaultPalette);
    const lower = ds[2];
    const xs = (lower.data as any[]).map((p) => new Date(p.x).toISOString());
    // union: start from raw[0], end from smoothed[1]
    expect(xs[0]).toBe('2025-11-03T12:00:00.000Z');
    expect(xs[1]).toBe('2025-11-03T12:15:00.000Z');
  });
});
