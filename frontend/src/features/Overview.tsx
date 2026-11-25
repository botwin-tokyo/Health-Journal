import SyncControl from "../components/SyncControl";
import { lazy, Suspense, useState } from "react";
import { Link } from "react-router";
import { usePage } from "../app/Shell";
import { records, useApi } from "../api/hooks";
import {
  Badge,
  Card,
  Empty,
  LoadState,
  Metric,
  Modal,
  Segments,
} from "../components/ui";
import {
  dateLabel,
  decimal,
  label,
  list,
  object,
  text,
  shiftDate,
} from "../lib/display";
import { latestObservation, latestMetrics } from "../lib/observations";
import { duration } from "./Sleep";
const Chart = lazy(() => import("../components/ChartFrame"));
export default function Overview() {
  const { date, range, setRange, readOnly } = usePage();
  const [slot, setSlot] = useState("morning"),
    [checkIn, setCheckIn] = useState(false);
  const query = useApi(
      `/api/v1/overview?date=${date}&from=${shiftDate(date, 1 - range)}&to=${date}&slot=${slot}&weight_unit=lb`,
      15000,
    ),
    journal = useApi(`/api/v1/journal/entries?from=${date}&to=${date}`),
    labs = useApi("/api/v1/labs/reports");
  const data = query.data || {},
    body = object(data.body),
    breathing = object(data.breathing),
    sleep = object(data.sleep_activity),
    weights = records(body.items),
    weight = weights.find((r) => r.id === body.representative_id) || records(body.representative_record ? [body.representative_record] : [])[0],
    session = object(breathing.selected_session),
    values = object(object(session.data).values),
    night = object(sleep.sleep),
    summary = object(night.stage_summary);
  const hr = latestObservation(sleep.observation_series, ["bpm", "heart_rate"]),
    readings = latestMetrics(sleep.observation_series),
    workouts = records(sleep.workouts);
  return (
    <div className="stack">
      <div className="row between">
        <Segments
          label="History range"
          values={["7", "28", "90", "365"]}
          value={String(range)}
          onChange={(v) => setRange(Number(v))}
        />
        {!readOnly && (
          <div className="row">
            <SyncControl />
            <button className="primary" onClick={() => setCheckIn(true)}>
              Add check-in
            </button>
          </div>
        )}
      </div>
      <LoadState loading={query.isPending} error={query.error}>
        <div
          className="metrics overviewMetrics"
          style={{ "--columns": 6 } as React.CSSProperties}
        >
          <Metric
            title="FEV1"
            value={values.fev1}
            unit="L"
            note={
              label(slot) +
              " · " +
              label(object(session.data).source_type || "not_recorded")
            }
          />
          <Metric
            title="Weight"
            value={weight?.data.display_value}
            unit="lb"
            note={
              weight
                ? "Morning · " + label(weight.data.source_type)
                : "No morning reading"
            }
          />
          <Metric
            title="Sleep"
            value={duration(summary.known_sleep_seconds)}
            note="Last completed session"
          />
          <Metric
            title="Heart rate"
            value={hr?.data.value}
            unit="bpm"
            note="Latest recorded reading"
          />
          <Metric
            title="Steps"
            value={object(sleep.steps).value}
            note={object(sleep.steps).method_version === "recorded-day-total-v1" ? "Phone · recorded daily total" : "Phone · recorded intervals"}
          />
          <Metric
            title="Exercise"
            value={
              workouts.length === 1
                ? duration(
                    object(workouts[0].daily_duration).seconds ??
                      object(workouts[0].daily_duration).value,
                  )
                : null
            }
            note="Completed activity"
          />
        </div>
        <Card title="Phone readings">
          <p className="small muted">Latest received reading for each metric on {dateLabel(date)}. Updates automatically.</p>
          {readings.length ? <div className="metrics">
            {readings.map(row => <Metric key={text(row.data.metric_id)}
              title={label(row.data.metric_id)} value={row.data.value} unit={text(row.data.unit, "")}
              note={`${label(row.data.source_type)} · ${row.data.measured_start ? text(row.data.measured_start) : "Recorded daily total"}`} />)}
          </div> : <Empty>No phone readings for this date.</Empty>}
          <Link to="/sleep-activity">View readings and charts →</Link>
          {sleep.cursor ? <p className="small muted">More readings are available in Sleep & activity.</p> : null}
        </Card>
        <div className="split">
          <div className="stack">
            <Card title="Breathing baseline">
              <div className="row between">
                <h2>FEV1 · selected session</h2>
                <Segments
                  label="Pulmonary reference slot"
                  values={["morning", "noon", "evening"]}
                  value={slot}
                  onChange={setSlot}
                />
              </div>
              <div className="grid2" style={{ marginTop: 20 }}>
                <div>
                  <p className="small muted">Current ({dateLabel(date)})</p>
                  <strong style={{ fontSize: 32 }}>
                    {text(values.fev1)} L
                  </strong>
                </div>
                <div>
                  <p className="small muted">Recent personal reference</p>
                  <strong style={{ fontSize: 32 }}>
                    {text(
                      object(object(breathing.recent_baselines).fev1).value,
                    )}{" "}
                    L
                  </strong>
                </div>
              </div>
              <p className="small muted">
                {label(
                  object(object(breathing.recent_baselines).fev1)
                    .absent_reason || "Same slot and comparable source",
                )}
              </p>
              <Link to="/breathing">Inspect session and references →</Link>
            </Card>
            <Suspense fallback={<div className="skeleton" />}>
              <Chart
                title="Weight trend"
                unit="lb"
                source="Original observations · morning designation shown in Body"
                points={weights.map((r) => ({
                  x: r.clinical_date || "",
                  value: decimal(r.data.display_value),
                  original: text(r.data.display_value),
                  revision: r.revision_id,
                }))}
              />
            </Suspense>
          </div>
          <div className="stack">
            <Card title="Daily check-ins">
              <div className="keyValue">
                <Link to="/body">Morning weight</Link>
                <span>
                  {weight ? (
                    <>
                      <Badge tone="soft">Recorded</Badge>{" "}
                      {text(weight.data.display_value)} lb
                    </>
                  ) : (
                    "Not recorded"
                  )}
                </span>
              </div>
              {["morning", "noon", "evening"].map((v) => (
                <div className="keyValue" key={v}>
                  <Link to="/breathing">{label(v)} breathing</Link>
                  <span>
                    {list(breathing.slot_coverage).includes(v) ? (
                      <Badge tone="soft">Recorded</Badge>
                    ) : (
                      "Not recorded"
                    )}
                  </span>
                </div>
              ))}
              <p className="small muted" style={{ marginTop: 12 }}>
                Daily minimum {breathing.minimum_met ? "met" : "not yet met"} ·{" "}
                {list(breathing.slot_coverage).length} of 3 preferred slots.
                Capture quality is separate.
              </p>
            </Card>
            <Card title="Journal highlights">
              {records(journal.data?.items).length ? (
                records(journal.data?.items)
                  .slice(0, 3)
                  .map((r) => (
                    <div className="keyValue" key={r.id}>
                      <div>
                        <Link to="/journal">
                          <strong>{text(r.data.title, "Journal entry")}</strong>
                        </Link>
                        <p className="small muted">
                          {dateLabel(r.clinical_date)}
                        </p>
                      </div>
                      <Badge>{label(r.data.visibility)}</Badge>
                    </div>
                  ))
              ) : (
                <Empty>No journal entries for this date.</Empty>
              )}
            </Card>
            <Card title="Latest lab report">
              {list(labs.data?.items).length ? (
                <>
                  <strong>
                    {text(
                      object(
                        object(object(list(labs.data?.items)[0]).review).data,
                      ).source_label,
                      "Laboratory report",
                    )}
                  </strong>
                  <div className="row">
                    <Badge>
                      {label(object(list(labs.data?.items)[0]).state)}
                    </Badge>
                    <Link to="/labs">Open reports →</Link>
                  </div>
                </>
              ) : (
                <Empty>No original laboratory report imported.</Empty>
              )}
            </Card>
          </div>
        </div>
        <Card title="Data coverage">
          <div className="metrics">
            {[
              ["Ring", "Qualified recorded intervals"],
              ["Phone", "Nightly upload, best effort"],
              ["Breathing", "Manual / reviewed import"],
              ["Weight", "Manual observation"],
            ].map(([title, description]) => (
              <div key={title}>
                <strong>{title}</strong>
                <p className="small muted">{description}</p>
              </div>
            ))}
          </div>
          <p className="small muted" style={{ marginTop: 16 }}>
            Upload time is not measurement time. The browser does not wake the
            phone or collect Bluetooth readings.
          </p>
        </Card>
      </LoadState>
      {checkIn && (
        <Modal title="Add check-in" onClose={() => setCheckIn(false)}>
          <div className="stack">
            <Link to="/body">Record morning weight</Link>
            <Link to="/breathing">Add breathing session</Link>
            <Link to="/journal">Write a private entry or medication event</Link>
          </div>
        </Modal>
      )}
    </div>
  );
}
