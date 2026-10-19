export type ChartPoint = { date: string; value: number | null };
export function utcTime(date: string) {
  return Date.parse(`${date}T00:00:00Z`);
}
export function chartDomain(values: number[], zero: boolean): [number, number] {
  const finite = values.filter(Number.isFinite);
  if (!finite.length) return [0, 1];
  const low = Math.min(...finite),
    high = Math.max(...finite);
  if (zero) {
    const min = Math.min(0, low),
      max = Math.max(0, high);
    if (min === 0 && max === 0) return [0, 1];
    const span = max - min;
    return [min < 0 ? min - span * 0.1 : 0, max > 0 ? max + span * 0.1 : 0];
  }
  const pad = Math.max((high - low) * 0.12, Math.abs(high) * 0.005, 0.000001);
  return [low - pad, high + pad];
}
export function lineSegments(points: ChartPoint[], maxGapDays: number): ChartPoint[][] {
  const result: ChartPoint[][] = [];
  let current: ChartPoint[] = [];
  for (const point of points) {
    if (point.value == null || !Number.isFinite(point.value)) {
      if (current.length) result.push(current);
      current = [];
      continue;
    }
    if (
      current.length &&
      utcTime(point.date) - utcTime(current[current.length - 1].date) > maxGapDays * 86400000
    ) {
      result.push(current);
      current = [];
    }
    current.push(point);
  }
  if (current.length) result.push(current);
  return result;
}
