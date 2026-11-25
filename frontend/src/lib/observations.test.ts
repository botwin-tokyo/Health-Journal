import { describe, expect, it } from "vitest";
import { latestObservation, latestMetrics } from "./observations";
const point = (id: string, metric: string, value: string, time: string) => ({
  id, revision_id: id, kind: "observation", version: 1, etag: id,
  clinical_date: "2026-11-09", data: {metric_id: metric, value, measured_start: time},
});
describe("phone observations", () => {
  it("shows the newest actual heart-rate reading without requiring a sample label or averaging sources", () => {
    const series = [
      {metric_id: "bpm", points: [point("a", "bpm", "68", "2026-11-09T08:00:00-05:00")]},
      {metric_id: "heart_rate", points: [point("b", "heart_rate", "72", "2026-11-09T15:00:00Z")]},
    ];
    expect(latestObservation(series, ["bpm", "heart_rate"])?.data.value).toBe("72");
  });
  it("preserves recorded zero and does not invent absent metrics", () => {
    const series = [{metric_id: "phone_steps", points: [point("a", "phone_steps", "0", "2026-11-09T08:00:00Z")]}];
    expect(latestMetrics(series)[0].data.value).toBe("0");
    expect(latestObservation(series, ["bpm"])).toBeUndefined();
  });
});
