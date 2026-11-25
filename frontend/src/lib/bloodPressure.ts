import type { ClinicalRecord } from "../api/hooks";
import { decimal, object, text } from "./display";
export const bpFields = {
  blood_pressure_systolic: "systolic",
  blood_pressure_diastolic: "diastolic",
  blood_pressure_pulse: "pulse",
} as const;
export type Reading = {
  id: string;
  at: string;
  verified: boolean;
  eligible: boolean;
  device: string;
  rows: ClinicalRecord[];
  systolic?: number;
  diastolic?: number;
  pulse?: number;
};
export function bloodPressureReadings(rows: ClinicalRecord[]): Reading[] {
  const grouped = new Map<string, Reading>();
  for (const row of rows) {
    const p = row.data,
      field = bpFields[p.metric_id as keyof typeof bpFields];
    if (!field) continue;
    const id = JSON.stringify([
      p.source_namespace,
      p.device_id,
      p.measurement_group_id || row.id,
    ]);
    const verified =
      p.timestamp_basis === "measurement" &&
      p.measurement_time_verified === true;
    const eligible =
      verified && p.clinical_eligible !== false && p.validity !== "unqualified";
    const reading = grouped.get(id) || {
      id,
      at: text(p.measured_start, row.clinical_date || ""),
      verified,
      eligible,
      device: text(p.device_model, "Blood-pressure monitor"),
      rows: [],
    };
    reading.verified &&= verified;
    reading.eligible &&= eligible;
    reading.rows.push(row);
    const value = decimal(p.value);
    if (value !== null) reading[field] = value;
    grouped.set(id, reading);
  }
  return [...grouped.values()].sort(
    (a, b) => (Date.parse(a.at) || 0) - (Date.parse(b.at) || 0),
  );
}
export function monitorFlags(reading: Reading): string[] {
  const native = object(reading.rows[0]?.data.native_record);
  return [
    ["bodyMovement", "Movement detected"],
    ["cuffLoose", "Loose cuff"],
    ["irregularHeartbeat", "Irregular heartbeat flag"],
  ]
    .filter(([key]) => native[key] === true)
    .map(([, label]) => label);
}
