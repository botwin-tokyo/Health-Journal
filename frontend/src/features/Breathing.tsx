import PhoneRecords from "../components/PhoneRecords";
import { lazy, Suspense, useState } from "react";
import { usePage } from "../app/Shell";
import { useApi, records } from "../api/hooks";
import {
  ActionFeedback,
  Badge,
  Card,
  Empty,
  LoadState,
  Metric,
  Modal,
  Provenance,
  Segments,
  useAction,
} from "../components/ui";
import { Timing, timing } from "../components/Timing";
import BaselineEditor from "../components/BaselineEditor";
import ExportPanel from "../components/ExportPanel";
import { decimal, label, list, object, text, shiftDate } from "../lib/display";
const Chart = lazy(() => import("../components/ChartFrame"));
export default function Breathing() {
  const { date, range, readOnly } = usePage();
  const [slot, setSlot] = useState("morning"),
    [selectedId, setSelectedId] = useState(""),
    [trialId, setTrialId] = useState(""),
    [add, setAdd] = useState(false),
    [baseline, setBaseline] = useState(false),
    [exportOpen, setExportOpen] = useState(false);
  const query = useApi(
      `/api/v1/breathing?date=${date}&from=${shiftDate(date, 1 - range)}&to=${date}&slot=${slot}`,
    ),
    data = query.data || {};
  const items = records(data.items);
  const selected =
    items.find((r) => r.id === selectedId) ||
    items.find((r) => r.id === object(data.selected_session).id) ||
    items.find((r) => r.data.slot === slot);
  const trials = list(selected?.data.trials).map(object);
  const trial =
    trials.find((t) => t.id === trialId) ||
    trials.find((t) => t.id === selected?.data.selected_trial_id) ||
    trials[0];
  const values = object(trial?.values || trial || selected?.data.values);
  const curves = object(trial?.curves || selected?.data.curves);
  const action = useAction();
  const points = (key: string) =>
    list(curves[key])
      .map((p) => {
        const a = Array.isArray(p) ? p : [];
        return {
          x: Number(a[0]),
          value: decimal(String(a[1])),
          original: text(a[1]),
        };
      })
      .filter((p) => Number.isFinite(p.x));
  return (
    <div className="stack">
      <div className="row between">
        <Segments
          values={["morning", "noon", "evening"]}
          value={slot}
          onChange={(value) => {
            setSlot(value);
            setSelectedId("");
            setTrialId("");
          }}
          label="Breathing slot"
        />
        <div className="row">
          <span>
            Minimum {data.minimum_met ? "met" : "not yet met"} · Preferred{" "}
            {list(data.slot_coverage).length}/3 slots
          </span>
          {!readOnly && (
            <button className="primary" onClick={() => setAdd(true)}>
              + Add session
            </button>
          )}
        </div>
      </div>
      <LoadState loading={query.isPending} error={query.error}>
        <Suspense fallback={<p>Loading history…</p>}>
          <Chart
            title="FEV1 history"
            unit="L"
            source={slot + " · designated sessions"}
            points={records(data.history).map((r) => ({
              x: r.clinical_date || "",
              value: decimal(object(r.data.values).fev1),
              original: text(object(r.data.values).fev1),
              revision: r.revision_id,
            }))}
          />
        </Suspense>
        <div className="metrics">
          {[
            ["fev1", "FEV1", "L"],
            ["fvc", "FVC", "L"],
            ["fev1_fvc", "FEV1/FVC", "%"],
            ["pef", "PEF", "L/min"],
          ].map(([key, name, unit]) => (
            <Metric
              key={key}
              title={name}
              value={
                key === "fev1_fvc" && decimal(values[key]) !== null
                  ? decimal(values[key])!.toFixed(1)
                  : values[key]
              }
              unit={unit}
              note={
                selected
                  ? label(selected.data.source_type) +
                    " · " +
                    (trial ? "Selected trial" : "Scalar observation")
                  : "No session in this slot"
              }
            />
          ))}
        </div>
        <div className="split">
          <div className="stack">
            <Card title={"FEV1 · " + label(slot) + " reference"}>
              <p className="value">
                {text(object(object(data.recent_baselines).fev1).value)} L
              </p>
              <p className="muted">
                {label(
                  object(object(data.recent_baselines).fev1).absent_reason ||
                    "Recent personal reference",
                )}
              </p>
              <button onClick={() => setBaseline(true)}>
                Reference details
              </button>
              <p className="small muted">
                Morning, noon and evening references remain separate. The
                selected day does not enter its recent reference.
              </p>
            </Card>
            <div className="grid2">
              <Suspense fallback={<div className="skeleton" />}>
                <Chart
                  title="Flow–volume"
                  points={points("flow_volume")}
                  numericX
                  unit="L/s · volume L"
                  source={label(
                    curves.provenance ||
                      selected?.data.curve_absent_reason ||
                      "Curve not supplied",
                  )}
                />
                <Chart
                  title="Volume–time"
                  points={points("volume_time")}
                  numericX
                  unit="L · time seconds"
                  source={label(
                    curves.provenance ||
                      selected?.data.curve_absent_reason ||
                      "Curve not supplied",
                  )}
                />
              </Suspense>
            </div>
            <Card title="Sessions on this date">
              {items.length ? (
                items.map((r) => (
                  <button
                    key={r.id}
                    className={
                      "listButton " + (r.id === selected?.id ? "selected" : "")
                    }
                    onClick={() => {
                      setSelectedId(r.id);
                      setTrialId("");
                    }}
                  >
                    <strong>
                      {r.data.slot ? label(r.data.slot) : "Unassigned session"}
                    </strong>
                    <small>
                      FEV1 {text(object(r.data.values).fev1)} L ·{" "}
                      {label(r.data.source_type)} ·{" "}
                      {label(r.data.capture_status)}
                    </small>
                  </button>
                ))
              ) : (
                <Empty>
                  One recorded session meets the daily minimum. Three assigned
                  slots meet preferred coverage.
                </Empty>
              )}
            </Card>
          </div>
          <Card title="Session detail">
            {selected ? (
              <div className="stack">
                <p>Source: {label(selected.data.source_type)}</p>
                {trials.length ? (
                  <div className="tableWrap">
                    <table>
                      <thead>
                        <tr>
                          <th>Trial</th>
                          <th>FEV1 (L)</th>
                          <th>FVC (L)</th>
                        </tr>
                      </thead>
                      <tbody>
                        {trials.map((t, i) => (
                          <tr key={text(t.id)}>
                            <td>
                              <label className="check">
                                <input
                                  type="radio"
                                  name="trial"
                                  checked={t === trial}
                                  onChange={() => setTrialId(text(t.id))}
                                />
                                Trial {i + 1}
                              </label>
                            </td>
                            <td>{text(object(t.values || t).fev1)}</td>
                            <td>{text(object(t.values || t).fvc)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p>
                    Scalar-only observation. No curve or extra maneuver is
                    inferred.
                  </p>
                )}
                <div className="row">
                  <Badge tone="soft">
                    {label(selected.data.capture_status)}
                  </Badge>
                  <Badge>Clinical quality not assessed</Badge>
                </div>
                <Provenance record={selected} />
                <details>
                  <summary>All supplied measurements</summary>
                  <dl>
                    {Object.entries(values)
                      .filter(
                        ([key, value]) =>
                          typeof value === "string" && key !== "id",
                      )
                      .map(([key, value]) => (
                        <div className="keyValue" key={key}>
                          <dt>{label(key)}</dt>
                          <dd>
                            {text(value)}{" "}
                            {text(object(selected.data.units)[key], "")}
                          </dd>
                        </div>
                      ))}
                  </dl>
                </details>
                {!readOnly && (
                  <>
                    <label className="field">
                      Organizational slot
                      <select
                        value={text(selected.data.slot, "")}
                        onChange={(event) =>
                          void action
                            .run(
                              "/api/v1/breathing/sessions/" +
                                selected.id +
                                "/designation",
                              {
                                slot: event.target.value || null,
                                make_representative: true,
                                reason: "Owner selected organizational slot",
                              },
                              { method: "PATCH", etag: selected.etag },
                            )
                            .catch(() => {})
                        }
                      >
                        <option value="">Unassigned</option>
                        {["morning", "noon", "evening"].map((v) => (
                          <option key={v}>{v}</option>
                        ))}
                      </select>
                    </label>
                    <button onClick={() => setExportOpen(true)}>
                      Export session
                    </button>
                    <a href="/journal">Add a private note in Journal</a>
                  </>
                )}
                <ActionFeedback action={action} />
              </div>
            ) : (
              <Empty>No session selected.</Empty>
            )}
          </Card>
        </div>
        <PhoneRecords date={date} domain="breathing" />
      </LoadState>
      {add && (
        <Modal title="Add breathing session" onClose={() => setAdd(false)}>
          <AddSession
            date={date}
            slot={slot}
            onSaved={() => {
              setAdd(false);
              void query.refetch();
            }}
          />
        </Modal>
      )}
      {baseline && (
        <Modal
          title="Personal breathing references"
          onClose={() => setBaseline(false)}
        >
          <BaselineEditor metric="fev1" slot={slot} />
        </Modal>
      )}
      {exportOpen && selected && (
        <Modal title="Export session" onClose={() => setExportOpen(false)}>
          <ExportPanel
            body={{ format: "breathing_session", record_id: selected.id }}
          />
        </Modal>
      )}
    </div>
  );
}
function AddSession({
  date,
  slot,
  onSaved,
}: {
  date: string;
  slot: string;
  onSaved: () => void;
}) {
  const [mode, setMode] = useState("manual");
  const action = useAction();
  return (
    <div className="stack">
      <Segments
        values={["manual", "csv"]}
        value={mode}
        onChange={setMode}
        label="Session source"
      />
      {mode === "manual" ? (
        <form
          className="form"
          onSubmit={(event) => {
            event.preventDefault();
            const fd = new FormData(event.currentTarget);
            const values = Object.fromEntries(
              ["fev1", "fvc", "pef", "fev6", "fet"]
                .filter((k) => String(fd.get(k) || "").trim())
                .map((k) => [k, String(fd.get(k))]),
            );
            void action
              .run("/api/v1/breathing/manual-sessions", {
                ...timing(fd),
                slot: fd.get("slot") || null,
                values,
              })
              .then(onSaved)
              .catch(() => {});
          }}
        >
          <Timing date={date} />
          <label className="field">
            Organizational slot
            <select name="slot" defaultValue={slot}>
              <option value="">Unassigned</option>
              {["morning", "noon", "evening"].map((v) => (
                <option key={v}>{v}</option>
              ))}
            </select>
          </label>
          <div className="grid2">
            {[
              ["fev1", "FEV1 (L)"],
              ["fvc", "FVC (L)"],
              ["pef", "PEF (L/min)"],
              ["fev6", "FEV6 (L)"],
              ["fet", "FET (s)"],
            ].map(([key, name]) => (
              <label className="field" key={key}>
                {name}
                <input
                  name={key}
                  inputMode="decimal"
                  pattern="[0-9]+([.][0-9]+)?"
                />
              </label>
            ))}
          </div>
          <p className="small muted">
            Enter reported scalar values. Curves and clinical quality are not
            inferred.
          </p>
          <ActionFeedback action={action} />
          <button className="primary" disabled={action.busy}>
            Save session
          </button>
        </form>
      ) : (
        <CsvReview date={date} />
      )}
    </div>
  );
}
function CsvReview({ date }: { date: string }) {
  const action = useAction(),
    [id, setId] = useState(""),
    [review, setReview] = useState<Record<string, unknown> | null>(null);
  const query = useApi(id ? "/api/v1/breathing/imports/" + id : null, !!id);
  const data = query.data || {};
  const rows = list(object(data.extraction).rows).map(list);
  return (
    <div className="stack">
      <label className="field">
        MIR CSV (up to 5 MiB)
        <input
          type="file"
          accept=".csv,text/csv"
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (!file) return;
            if (file.size > 5242880) {
              action.setError(Error("CSV too large"));
              return;
            }
            void action
              .run(
                "/api/v1/breathing/imports",
                new Blob([file], { type: "text/csv" }),
              )
              .then((value) => setId(text(object(value).id)))
              .catch(() => {});
          }}
        />
      </label>
      {id && (
        <p role="status">
          {label(data.state || "uploaded")} · {label(data.parse_state)}
        </p>
      )}
      {rows.length > 1 && (
        <form
          className="form"
          onSubmit={(event) => {
            event.preventDefault();
            const fd = new FormData(event.currentTarget);
            const sessions: unknown[] = [],
              excluded_rows: Record<string, string> = {};
            rows.slice(1).forEach((row, index) => {
              const ordinal = index + 1;
              if (fd.has("exclude-" + ordinal)) {
                excluded_rows[String(ordinal)] = String(
                  fd.get("reason-" + ordinal) || "Owner excluded row",
                );
                return;
              }
              sessions.push({
                clinical_date: fd.get("date-" + ordinal),
                time_precision: "day",
                slot: fd.get("slot-" + ordinal) || null,
                source_rows: [ordinal],
                values: Object.fromEntries(
                  ["fev1", "fvc", "pef"]
                    .filter((k) => fd.get(k + "-" + ordinal))
                    .map((k) => [k, fd.get(k + "-" + ordinal)]),
                ),
              });
            });
            void action
              .run(
                "/api/v1/breathing/imports/" + id + "/review",
                {
                  sessions,
                  excluded_rows,
                  unknown_columns_acknowledged: fd.has("ack"),
                },
                { method: "PATCH", etag: text(data.etag) },
              )
              .then((value) => setReview(object(value)))
              .catch(() => {});
          }}
        >
          <p>
            Review the original columns and map each row. No extraction is
            published automatically.
          </p>
          <div className="tableWrap">
            <table>
              <thead>
                <tr>
                  {rows[0].map((c, i) => (
                    <th key={i}>{text(c)}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.slice(1).map((row, i) => (
                  <tr key={i}>
                    {row.map((c, j) => (
                      <td key={j}>{text(c)}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {rows.slice(1).map((_row, index) => (
            <Card key={index} title={"Source row " + (index + 1)}>
              <label className="field">
                Recorded date
                <input
                  type="date"
                  name={"date-" + (index + 1)}
                  defaultValue={date}
                />
              </label>
              <label className="field">
                Slot
                <select name={"slot-" + (index + 1)}>
                  <option value="">Unassigned</option>
                  <option>morning</option>
                  <option>noon</option>
                  <option>evening</option>
                </select>
              </label>
              <div className="grid2">
                {["fev1", "fvc", "pef"].map((k) => (
                  <label className="field" key={k}>
                    {k.toUpperCase()} ({k === "pef" ? "L/min" : "L"})
                    <input name={k + "-" + (index + 1)} inputMode="decimal" />
                  </label>
                ))}
              </div>
              <label className="check">
                <input name={"exclude-" + (index + 1)} type="checkbox" />
                Exclude this row
              </label>
              <label className="field">
                Exclusion reason
                <input name={"reason-" + (index + 1)} />
              </label>
            </Card>
          ))}
          <label className="check">
            <input name="ack" type="checkbox" required />I reviewed units,
            dates, duplicate rows and unmapped columns.
          </label>
          <button disabled={action.busy}>Save reviewed mapping</button>
        </form>
      )}
      {(review?.state === "reviewed" || data.state === "reviewed") && (
        <button
          className="primary"
          disabled={action.busy}
          onClick={() =>
            void action
              .run(
                "/api/v1/breathing/imports/" + id + "/commit",
                {},
                { etag: text(review?.etag || data.etag) },
              )
              .catch(() => {})
          }
        >
          Commit reviewed sessions
        </button>
      )}
      <ActionFeedback action={action} />
    </div>
  );
}
