import { displayTimezone } from "../lib/site";
import { useState } from "react";
export function Timing({
  date,
  lockDate = false,
  initial = {},
}: {
  date: string;
  lockDate?: boolean;
  initial?: Record<string, unknown>;
}) {
  const recorded =
    typeof initial.measured_start === "string" ? initial.measured_start : "";
  const [precise, setPrecise] = useState(
    !!recorded && initial.time_precision !== "day",
  );
  const offset =
    typeof initial.original_offset_minutes === "number"
      ? initial.original_offset_minutes
      : null;
  const offsetText =
    offset === null
      ? ""
      : (offset < 0 ? "-" : "+") +
        String(Math.floor(Math.abs(offset) / 60)).padStart(2, "0") +
        ":" +
        String(Math.abs(offset) % 60).padStart(2, "0");
  const instant = Date.parse(recorded);
  const clock =
    Number.isFinite(instant) && offset !== null
      ? new Date(instant + offset * 60000).toISOString().slice(11, 16)
      : "";
  return (
    <fieldset style={{ border: 0, padding: 0, margin: 0 }}>
      <legend className="srOnly">Recorded date and time</legend>
      <label className="field">
        Date
        <input
          name="clinical_date"
          type="date"
          defaultValue={date}
          readOnly={lockDate}
          required
        />
      </label>
      <label className="check">
        <input
          type="checkbox"
          checked={!precise}
          onChange={(e) => setPrecise(!e.target.checked)}
        />
        Time not recorded (date only)
      </label>
      <input
        type="hidden"
        name="time_precision"
        value={precise ? "minute" : "day"}
      />
      {precise && (
        <div className="grid2">
          <label className="field">
            Recorded time
            <input type="time" name="time" defaultValue={clock} required />
          </label>
          <label className="field">
            Recorded timezone
            <input
              name="timezone"
              defaultValue={
                typeof initial.timezone === "string"
                  ? initial.timezone
                  : displayTimezone
              }
              required
            />
          </label>
          <label className="field">
            Recorded UTC offset
            <input
              name="offset"
              defaultValue={offsetText}
              placeholder="−05:00"
              pattern="[+-][0-9]{2}:[0-9]{2}"
              required
            />
          </label>
          <p className="small muted">
            Enter the offset for that observation. Ambiguous daylight-saving
            times require an explicit offset.
          </p>
        </div>
      )}
    </fieldset>
  );
}
export function timing(form: FormData) {
  const clinical_date = String(form.get("clinical_date")),
    precision = String(form.get("time_precision") || "day");
  if (precision === "day")
    return { clinical_date, time_precision: "day", measured_start: null };
  const offset = String(form.get("offset"));
  const minutes =
    (Number(offset.slice(1, 3)) * 60 + Number(offset.slice(4))) *
    (offset.startsWith("-") ? -1 : 1);
  return {
    clinical_date,
    time_precision: "minute",
    measured_start: clinical_date + "T" + form.get("time") + ":00" + offset,
    timezone: String(form.get("timezone")),
    original_offset_minutes: minutes,
  };
}
