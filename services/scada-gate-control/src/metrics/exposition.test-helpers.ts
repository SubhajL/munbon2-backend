/**
 * Test-only helpers for reading Prometheus exposition text. Excluded from the production
 * build (see tsconfig `exclude`). Single source of truth so the exposition parser is not
 * forked across spec files.
 */

/** Read the numeric value of a single `name{label="v"} N` series from exposition text. */
export function readSeriesValue(body: string, series: string): number | undefined {
  const line = body.split('\n').find((l) => l.startsWith(series + ' '));
  return line === undefined ? undefined : Number(line.slice(series.length + 1));
}
