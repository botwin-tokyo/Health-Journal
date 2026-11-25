import { displayTimezone } from "../lib/site";
import PhoneRecords from "../components/PhoneRecords";
import { lazy, Suspense, useId, useState } from "react";
import { usePage } from "../app/Shell";
import { records, useApi, type ClinicalRecord } from "../api/hooks";
import {
  Badge,
  Card,
  Empty,
  LoadState,
  Metric,
  Modal,
  Provenance,
  Segments,
} from "../components/ui";
import { decimal, label, list, object, text } from "../lib/display";
import { latestObservation } from "../lib/observations";
const Chart = lazy(() => import("../components/ChartFrame"));
export function duration(seconds: unknown) {
  if(typeof seconds === "string") seconds=decimal(seconds);
  if (typeof seconds !== "number" || !Number.isFinite(seconds)) return null;
  const minutes = Math.floor(seconds / 60);
  return (
    Math.floor(minutes / 60) +
    "h " +
    String(minutes % 60).padStart(2, "0") +
    "m"
  );
}
export default function Sleep() {
  const { date } = usePage();
  const [source, setSource] = useState("phone"),
    [workout, setWorkout] = useState<ClinicalRecord | null>(null);
  const [pageCursor, setPageCursor] = useState({ date, source, cursor: "" });
  const cursor = pageCursor.date === date && pageCursor.source === source ? pageCursor.cursor : "";
  const query = useApi(
      `/api/v1/sleep-activity?date=${date}&steps_source=${source}${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`,
      15000,
    ),
    catalog = useApi("/api/v1/catalog/metrics");
  const data = query.data || {},
    sleep = object(data.sleep),
    payload = object(sleep.data),
    summary = object(sleep.stage_summary),
    stages = object(summary.stage_seconds),
    workouts = records(data.workouts),
    sleepSessions = records(data.sleep_sessions),
    stepRows = records(data.step_records),
    series = list(data.observation_series).map(object),
    steps = object(data.steps);
  return (
    <div className="stack">
      <div className="row between">
        <p className="muted">Wake date {date} · All received sessions</p>
        <Badge>Recorded sleep and activity</Badge>
      </div>
      <LoadState loading={query.isPending} error={query.error}>
        <div className="metrics">
          <Metric
            title="Recorded sleep"
            value={duration(summary.known_sleep_seconds)}
            note={payload.measured_start ? `${text(sleep.display_status)} · ${summary.known_sleep_seconds == null ? "Sleep duration not supplied" : label(payload.source_type)}` : label(data.sleep_absent_reason)}
          />
          <Metric
            title="Session span"
            value={duration(summary.span_seconds)}
            note="Includes awake and unknown intervals"
          />
          <Metric
            title="Unknown"
            value={duration(stages.unknown)}
            note="Unclassified time is not sleep"
          />
          <Metric
            title={source === "phone" ? "Phone steps" : "Ring steps"}
            value={steps.value}
            note={label(steps.absent_reason || "Recorded intervals")}
          />
          <Metric
            title="Completed exercise"
            value={duration(data.workout_total_seconds)}
            note={`${text(data.completed_workout_count, "0")} completed workouts · recorded active duration`}
          />
        </div>
        <div className="split">
          <div className="stack">
            <Card title="Sleep stages">
              {list(payload.stages).length ? (
                <>
                  <p className="small muted">
                    {text(payload.measured_start)} –{" "}
                    {text(payload.measured_end)}
                  </p>
                  <StageTimeline
                    start={text(payload.measured_start, "")}
                    end={text(payload.measured_end, "")}
                    intervals={list(payload.stages).map(object)}
                  />
                  <h3>Stage distribution</h3>
                  {["light", "deep", "rem", "awake", "unknown"].map((stage) => (
                    <div className="keyValue" key={stage}>
                      <strong>{label(stage)}</strong>
                      <span>{duration(stages[stage]) || "Unavailable"}</span>
                    </div>
                  ))}
                  <p className="small muted">
                    {label(payload.qualification)} ·{" "}
                    {label(summary.method_version)}. Unknown periods remain
                    unclassified.
                  </p>
                </>
              ) : (
                <Empty>
                  {sleepSessions.length ? "Sessions received, but no sleep stages were supplied for the selected session." : "No sleep session received for this wake date."}
                </Empty>
              )}
            </Card>
            <Card title="Sleep sessions">
              {!sleepSessions.length && <Empty>No sleep sessions for this date.</Empty>}
              {sleepSessions.map(row => <div className="card" key={row.id}>
                <h3>{row.data.complete ? "Recorded session" : "Partial session"} · {label(row.data.source_type)}</h3>
                <p>{text(row.data.measured_start)} – {text(row.data.measured_end)}</p>
                <p>Session span: {duration(object(row.stage_summary).span_seconds) || "Not supplied"}</p>
                <p>Measured sleep: {duration(object(row.stage_summary).known_sleep_seconds) || "Not supplied"}</p>
                <p>{list(row.data.stages).length ? `${list(row.data.stages).length} recorded stage intervals` : "Sleep stages not supplied"}</p>
                {!row.data.complete && <p className="small muted">Reported as incomplete by the source. Session span is not measured sleep time.</p>}
              </div>)}
            </Card>
            <Card title="Activity across the day">
              <div className="row between">
                <h3>Steps by source</h3>
                <Segments
                  label="Step source"
                  values={["phone", "ring"]}
                  value={source}
                  onChange={setSource}
                />
              </div>
              <p className="value">{text(steps.value)} steps</p>
              <p className="small muted">
                {steps.method_version === "recorded-day-total-v1"
                  ? "Recorded daily total."
                  : `${text(steps.covered_seconds, "0")} recorded seconds · ${text(steps.excluded_intervals, "0")} excluded intervals.`} Phone
                and ring totals are never added.
              </p>
              <div className="tableWrap">
                <table>
                  <thead>
                    <tr>
                      <th>Interval start</th>
                      <th>Interval end</th>
                      <th>Steps</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(stepRows.length ? stepRows : series
                      .filter(g => g.metric_id === (source === "phone" ? "phone_steps" : "ring_step_subtotal"))
                      .flatMap(g => records(g.points)))
                      .map((r) => (
                        <tr key={r.id}>
                          <td>{text(r.data.measured_start, r.clinical_date || "—")}</td>
                          <td>{text(r.data.measured_end, "Daily total")}</td>
                          <td>{text(r.data.value)}</td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            </Card>
          </div>
          <div className="stack">
            <Card title="Recorded observations">
              {!series.length && (
                <Empty>Awaiting qualified observations.</Empty>
              )}
              {series
                .filter(
                  (s) =>
                    s.metric_id !== "phone_steps" &&
                    s.metric_id !== "ring_step_subtotal",
                )
                .map((group) => (
                  <div key={text(group.series_id)} className="stack">
                    <div className="row between">
                      <strong>{label(group.metric_id)}</strong>
                      <Badge>{label(group.qualification)}</Badge>
                    </div>
                    <p>
                      {text(object(group.daily_summary).value ?? latestObservation([group], [text(group.metric_id)])?.data.value)}{" "}
                      {text(group.unit, "")}{" "}
                      <span className="small muted">
                        {label(
                          object(group.daily_summary).value != null
                            ? object(group.daily_summary).method_version
                            : "Latest recorded reading",
                        )}
                      </span>
                    </p>
                    <Suspense fallback={<div className="skeleton" />}>
                      <Chart
                        title={label(group.metric_id)}
                        unit={text(group.unit, "")}
                        source={label(group.statistic)}
                        points={records(group.points).map((r) => ({
                          x: text(r.data.measured_start, r.clinical_date || ""),
                          value: decimal(r.data.value),
                          original: text(r.data.value),
                          revision: r.revision_id,
                        }))}
                      />
                    </Suspense>
                  </div>
                ))}
            </Card>
            <Card title="Completed workout">
              {workouts.length ? (
                workouts.map((row) => (
                  <button
                    className="listButton"
                    key={row.id}
                    onClick={() => setWorkout(row)}
                  >
                    <strong>
                      {text(
                        row.data.name || row.data.routine_name || object(row.data.routine_snapshot).name || label(row.data.activity),
                        "Recorded workout",
                      )}
                    </strong>
                    <small>
                      {label(row.data.state)} · {duration(object(row.daily_duration).value) || "Duration not supplied"} ·{" "}
                      {label(
                        object(row.daily_duration).absent_reason ||
                          "Includes recorded rest; pauses excluded",
                      )}
                    </small>
                  </button>
                ))
              ) : (
                <Empty>No recorded workout on this date.</Empty>
              )}
            </Card>
          </div>
        </div>
        <Card title="Coverage & sources">
          <p>
            Recorded intervals describe source coverage, not guaranteed
            continuous physiological validity.
          </p>
          <p className="small muted">
            Skin temperature is not core temperature. RMSSD and SDNN are
            distinct methods. Stress scores do not measure anxiety. Console,
            modeled gross and modeled active calories remain separate.
          </p>
          <details>
            <summary>More observations and source capabilities</summary>
            <div className="tableWrap">
              <table>
                <thead>
                  <tr>
                    <th>Observation</th>
                    <th>Capability</th>
                    <th>Availability</th>
                    <th>Unit</th>
                  </tr>
                </thead>
                <tbody>
                  {list(catalog.data?.metrics)
                    .map(object)
                    .filter((r) => r.chart_eligible === true)
                    .map((r) => (
                      <tr key={text(r.key)}>
                        <td>{label(r.key)}</td>
                        <td>{label(r.capability_status)}</td>
                        <td>{label(r.availability)}</td>
                        <td>{text(r.unit)}</td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </details>
        </Card>
        {records(data.source_records).length > 0 && <Card title="Other phone records">
          {records(data.source_records).map(row => <details key={row.id}>
            <summary>{label(row.data.source_kind)} · {row.clinical_date}</summary>
            <pre style={{whiteSpace: "pre-wrap", overflowWrap: "anywhere"}}>{JSON.stringify(row.data, null, 2)}</pre>
          </details>)}
        </Card>}
        <div className="row">
          {cursor && <button onClick={() => setPageCursor({date, source, cursor: ""})}>First readings</button>}
          {data.cursor ? <button onClick={() => setPageCursor({date, source, cursor: text(data.cursor, "")})}>Next readings</button> : null}
        </div>
        <PhoneRecords date={date} domain="sleep" />
      </LoadState>
      {workout && (
        <Modal title="Workout details" onClose={() => setWorkout(null)}>
          <Provenance record={workout} />
          <dl>
            {Object.entries(workout.data)
              .filter(([, v]) => typeof v === "string" || typeof v === "number")
              .map(([key, value]) => (
                <div className="keyValue" key={key}>
                  <dt>{label(key)}</dt>
                  <dd>{text(value)}</dd>
                </div>
              ))}
          </dl>
          <p className="small muted">
            Duration and calorie methods are supplied by the backend. Missing or
            clock-discontinuous totals remain unavailable.
          </p>
        </Modal>
      )}
    </div>
  );
}
function StageTimeline({
  start,
  end,
  intervals,
}: {
  start: string;
  end: string;
  intervals: Record<string, unknown>[];
}) {
  const id = useId().replaceAll(":", ""),
    left = Date.parse(start),
    right = Date.parse(end),
    names = ["awake", "rem", "light", "deep", "unknown"];
  if (!Number.isFinite(left) || !Number.isFinite(right) || right <= left)
    return <Empty>Stage timing unavailable.</Empty>;
  const x = (value: unknown) =>
    90 + ((Date.parse(String(value)) - left) / (right - left)) * 500;
  return (
    <>
      <svg
        viewBox="0 0 620 230"
        role="img"
        aria-label="Recorded sleep-stage intervals; unknown intervals are hatched"
        style={{ width: "100%", minHeight: 220 }}
      >
        <defs>
          <pattern id={id} patternUnits="userSpaceOnUse" width="6" height="6">
            <path d="M0 6L6 0" stroke="#85878d" strokeWidth="1" />
          </pattern>
        </defs>
        {names.map((stage, index) => (
          <g key={stage}>
            <text x="0" y={32 + index * 35} fontSize="13" fill="#5e6066">
              {label(stage)}
            </text>
            <line
              x1="90"
              x2="590"
              y1={34 + index * 35}
              y2={34 + index * 35}
              stroke="#e7e7e4"
            />
          </g>
        ))}
        {intervals.map((r, i) => (
          <rect
            key={i}
            x={x(r.start)}
            y={18 + Math.max(0, names.indexOf(text(r.stage))) * 35}
            width={Math.max(0, x(r.end) - x(r.start))}
            height="18"
            fill={
              r.stage === "unknown"
                ? `url(#${id})`
                : r.stage === "deep"
                  ? "#36373a"
                  : "#85878d"
            }
          />
        ))}
        <text x="90" y="222" fontSize="12">
          {new Date(left).toLocaleTimeString("en-US", {
            hour: "2-digit",
            minute: "2-digit",
            timeZone: displayTimezone,
          })}
        </text>
        <text x="530" y="222" fontSize="12">
          {new Date(right).toLocaleTimeString("en-US", {
            hour: "2-digit",
            minute: "2-digit",
            timeZone: displayTimezone,
          })}
        </text>
      </svg>
      <details>
        <summary>Stage interval table</summary>
        <div className="tableWrap">
          <table>
            <thead>
              <tr>
                <th>Start</th>
                <th>End</th>
                <th>Stage</th>
              </tr>
            </thead>
            <tbody>
              {intervals.map((r, i) => (
                <tr key={i}>
                  <td>{text(r.start)}</td>
                  <td>{text(r.end)}</td>
                  <td>{label(r.stage)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </>
  );
}
