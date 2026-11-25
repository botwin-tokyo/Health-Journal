import { records, type ClinicalRecord } from "../api/hooks";
import { list, object, text } from "./display";

export function observationTime(row: ClinicalRecord): number {
  return Date.parse(text(row.data.measured_end || row.data.measured_start, `${row.clinical_date}T00:00:00Z`)) || 0;
}

export function latestObservation(series: unknown, metrics: string[]): ClinicalRecord | undefined {
  return list(series).map(object)
    .filter(group => metrics.includes(text(group.metric_id)))
    .flatMap(group => records(group.points))
    .sort((a, b) => observationTime(b) - observationTime(a) ||
      text(b.received_at).localeCompare(text(a.received_at)))[0];
}

export function latestMetrics(series: unknown): ClinicalRecord[] {
  const metrics = [...new Set(list(series).map(object).map(group => text(group.metric_id)))];
  return metrics.map(metric => latestObservation(series, [metric])).filter((row): row is ClinicalRecord => !!row);
}
