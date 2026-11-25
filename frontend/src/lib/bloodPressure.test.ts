import { describe, expect, it } from "vitest";
import { bloodPressureReadings, monitorFlags } from "./bloodPressure";
import type { ClinicalRecord } from "../api/hooks";
const row = (metric: string, value: string, extra = {}): ClinicalRecord => ({
  id: metric,
  revision_id: metric,
  kind: "blood_pressure",
  version: 1,
  etag: "one",
  data: {
    metric_id: metric,
    value,
    measurement_group_id: "same",
    device_id: "monitor",
    source_namespace: "phone",
    timestamp_basis: "measurement",
    measurement_time_verified: true,
    clinical_eligible: true,
    measured_start: "2020-01-02T10:00:00-05:00",
    ...extra,
  },
});
describe("blood pressure history", () => {
  it("pairs only the same device, namespace and measurement", () => {
    const rows = bloodPressureReadings([
      row("blood_pressure_systolic", "118"),
      row("blood_pressure_diastolic", "77"),
      row("blood_pressure_pulse", "73"),
      row("blood_pressure_systolic", "130", { device_id: "other" }),
    ]);
    expect(rows).toHaveLength(2);
    expect(rows[0]).toMatchObject({
      systolic: 118,
      diastolic: 77,
      pulse: 73,
      eligible: true,
    });
  });
  it("keeps bad-clock and flagged readings visible but out of trends", () => {
    const [reading] = bloodPressureReadings([
      row("blood_pressure_systolic", "118", {
        timestamp_basis: "phone_received",
        measurement_time_verified: false,
        native_record: { cuffLoose: true },
      }),
    ]);
    expect(reading.systolic).toBe(118);
    expect(reading.eligible).toBe(false);
    expect(monitorFlags(reading)).toEqual(["Loose cuff"]);
  });
});
