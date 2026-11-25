import { lazy, Suspense, useRef, useState } from "react";
import { usePage } from "../app/Shell";
import { useApi, records } from "../api/hooks";
import {
  ActionFeedback,
  Badge,
  Card,
  DirtyGuard,
  Empty,
  LoadState,
  Modal,
  Segments,
  useAction,
} from "../components/ui";
import { dateLabel, decimal, label, list, object, text } from "../lib/display";
const Chart = lazy(() => import("../components/ChartFrame"));
const DocumentViewer = lazy(() => import("../components/DocumentViewer"));
export default function Labs() {
  const { readOnly } = usePage();
  const reports = useApi("/api/v1/labs/reports"),
    trends = useApi("/api/v1/labs/trends");
  const [id, setId] = useState(""),
    [tab, setTab] = useState("results"),
    [original, setOriginal] = useState(false),
    [editing, setEditing] = useState(false);
  const items = list(reports.data?.items).map(object);
  const selected = id || text(items[0]?.id, "");
  const report = useApi(
      selected ? "/api/v1/labs/reports/" + selected : null,
      true,
    ),
    data = report.data || {},
    review = object(object(data.review).data);
  const rows = list(review.results)
    .map(object)
    .filter((r) => !r.excluded);
  const granted = records(data.results);
  const action = useAction();
  return (
    <div className="stack">
      <div className="row between">
        <p className="muted">
          PDF import is available. Direct laboratory connectors remain
          unavailable.
        </p>
        {!readOnly && (
          <label className="field">
            Import report · PDF up to 25 MiB
            <input
              type="file"
              accept="application/pdf,.pdf"
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (!file) return;
                if (file.size > 26214400) {
                  action.setError(Error("PDF exceeds 25 MiB"));
                  return;
                }
                void action
                  .run(
                    "/api/v1/labs/uploads",
                    new Blob([file], { type: "application/pdf" }),
                  )
                  .then((value) => {
                    setId(text(object(value).id));
                    setOriginal(false);
                    setEditing(true);
                  })
                  .catch(() => {});
              }}
            />
          </label>
        )}
      </div>
      <ActionFeedback action={action} />
      <div className="tri">
        <Card title="Reports">
          <LoadState loading={reports.isPending} error={reports.error}>
            {items.length ? (
              items.map((item) => (
                <button
                  key={text(item.id)}
                  className={
                    "listButton " + (item.id === selected ? "selected" : "")
                  }
                  onClick={() => {
                    setId(text(item.id));
                    setOriginal(false);
                    setEditing(false);
                  }}
                >
                  <strong>
                    {text(
                      object(object(item.review).data).source_label,
                      "Laboratory report",
                    )}
                  </strong>
                  <small>
                    {dateLabel(
                      text(object(object(item.review).data).clinical_date, ""),
                    )}
                  </small>
                  <Badge tone={item.state === "needs_review" ? "red" : "soft"}>
                    {label(item.state)}
                  </Badge>
                </button>
              ))
            ) : (
              <Empty>Import an original PDF to begin.</Empty>
            )}
          </LoadState>
        </Card>
        <div className="stack">
          <Card title="Reviewed results">
            <LoadState
              loading={!!selected && report.isPending}
              error={report.error}
            >
              {selected ? (
                <>
                  <div className="row between">
                    <Badge>{label(data.state)}</Badge>
                    <span className="small muted">
                      Collection {dateLabel(text(review.clinical_date, ""))}
                    </span>
                  </div>
                  <Segments
                    label="Report workspace"
                    values={["results", "trends", "details"]}
                    value={tab}
                    onChange={setTab}
                  />
                  {tab === "results" ? (
                    <ResultTable
                      rows={
                        granted.length
                          ? granted.map((r) => r.data)
                          : data.state === "reviewed"
                            ? rows
                            : []
                      }
                    />
                  ) : tab === "trends" ? (
                    <>
                      <p className="small muted">
                        Sparse collection dates remain separate observations.
                        Inequalities are bounds, not exact points.
                      </p>
                      <LabTrends data={trends.data} />
                    </>
                  ) : (
                    <dl>
                      <div className="keyValue">
                        <dt>Source report status</dt>
                        <dd>{label(review.source_report_status)}</dd>
                      </div>
                      <div className="keyValue">
                        <dt>Fasting</dt>
                        <dd>{label(review.fasting || "unknown")}</dd>
                      </div>
                      <div className="keyValue">
                        <dt>Parser</dt>
                        <dd>{label(data.parse_state)}</dd>
                      </div>
                      <div className="keyValue">
                        <dt>Supersedes report</dt>
                        <dd>{text(review.supersedes_report_id)}</dd>
                      </div>
                    </dl>
                  )}
                  {data.state !== "reviewed" && (
                    <p className="notice">
                      Unreviewed extraction is excluded from normal trends and
                      appointment reports.
                    </p>
                  )}
                  {!readOnly && (
                    <button
                      disabled={
                        !["ready", "failed"].includes(text(data.parse_state))
                      }
                      onClick={() => setEditing(true)}
                    >
                      Review transcription
                    </button>
                  )}
                </>
              ) : (
                <Empty>Select an original report.</Empty>
              )}
            </LoadState>
          </Card>
          <Card title="Result interpretation">
            <p className="small muted">
              Original inequalities, units and reporting-laboratory ranges are
              preserved. A source flag is not a diagnosis or a treatment
              recommendation.
            </p>
          </Card>
        </div>
        <Card title="Original report">
          {data.document_id ? (
            <div className="stack">
              <button
                disabled={
                  data.parse_state !== undefined && data.parse_state !== "ready"
                }
                onClick={() => setOriginal(!original)}
              >
                {original ? "Close original" : "Open original"}
              </button>
              {original && (
                <Suspense fallback={<div className="skeleton" />}>
                  <DocumentViewer
                    key={text(data.document_id)}
                    documentId={text(data.document_id)}
                  />
                </Suspense>
              )}
              <details>
                <summary>Local extraction</summary>
                <p className="note small">
                  {text(
                    object(data.extraction).text,
                    "No extraction text available.",
                  )}
                </p>
                {list(object(data.extraction).pages).map((value, index) => (
                  <p className="note small" key={index}>
                    {text(object(value).text)}
                  </p>
                ))}
              </details>
            </div>
          ) : (
            <Empty>
              {readOnly
                ? "The original document is not shared in this view."
                : "No original selected."}
            </Empty>
          )}
        </Card>
      </div>
      {editing && selected && report.data && (
        <Modal
          title="Review laboratory transcription"
          onClose={() => setEditing(false)}
        >
          <LabReview
            key={selected}
            id={selected}
            report={report.data}
            onDone={() => {
              setEditing(false);
              void report.refetch();
              void reports.refetch();
            }}
          />
        </Modal>
      )}
    </div>
  );
}
function ResultTable({ rows }: { rows: Record<string, unknown>[] }) {
  return rows.length ? (
    <div className="tableWrap">
      <table>
        <thead>
          <tr>
            <th>Collection date</th>
            <th>Test</th>
            <th>Result</th>
            <th>Unit</th>
            <th>Reference</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              <td>
                {row.clinical_date
                  ? dateLabel(text(row.clinical_date))
                  : "Not recorded"}
              </td>
              <th scope="row">{text(row.label)}</th>
              <td>
                <strong>{text(row.raw_result_text)}</strong>
              </td>
              <td>{text(row.unit)}</td>
              <td>{text(row.reference_text)}</td>
              <td>
                {row.lab_flag ? (
                  <Badge tone="red">Lab-flagged: {text(row.lab_flag)}</Badge>
                ) : (
                  <span className="muted">No source flag</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  ) : (
    <Empty>No published results in this scope.</Empty>
  );
}
function LabTrends({ data }: { data: Record<string, unknown> | undefined }) {
  const groups = list(data?.series).map(object);
  return groups.length ? (
    groups.map((group, i) => (
      <div key={i}>
        <h3>{text(group.label || group.analyte, "Comparable results")}</h3>
        <Suspense fallback={<p>Loading result trend…</p>}>
          <Chart
            title={text(
              object(object(list(group.points)[0]).data).label,
              "Result trend",
            )}
            unit={text(group.unit, "")}
            source="Reviewed comparable results · source operators preserved below"
            points={list(group.points)
              .map(object)
              .filter((r) => r.clinical_date)
              .map((r) => ({
                x: text(r.clinical_date),
                value:
                  r.plot_kind === "point"
                    ? decimal(object(r.data).value)
                    : null,
                original: text(object(r.data).raw_result_text),
                revision: text(r.revision_id),
              }))}
          />
        </Suspense>
        <p className="small muted">
          Bounded and text results are shown in the dated table; they are not
          treated as exact numeric points.
        </p>
        <ResultTable
          rows={list(group.points)
            .map(object)
            .map((r) => ({
              ...object(r.data),
              clinical_date: r.clinical_date,
            }))}
        />
      </div>
    ))
  ) : (
    <ResultTable rows={records(data?.items).map((r) => r.data)} />
  );
}
function LabReview({
  id,
  report,
  onDone,
}: {
  id: string;
  report: Record<string, unknown>;
  onDone: () => void;
}) {
  const original = object(object(report.review).data);
  const [count, setCount] = useState(
      Math.max(1, list(original.results).length),
    ),
    [dirty, setDirty] = useState(false),
    [saved, setSaved] = useState<Record<string, unknown> | null>(null);
  const ref = useRef<HTMLFormElement>(null),
    action = useAction();
  const rows = list(original.results).map(object);
  async function save() {
    if (!ref.current?.reportValidity()) return false;
    const fd = new FormData(ref.current);
    const results = Array.from({ length: count }, (_, i) => ({
      label: fd.get("label-" + i),
      raw_result_text: fd.get("raw-" + i),
      value_kind: fd.get("kind-" + i),
      value: fd.get("kind-" + i) === "numeric" ? fd.get("value-" + i) : null,
      operator: fd.get("operator-" + i),
      unit: fd.get("unit-" + i) || null,
      reference_text: fd.get("range-" + i) || null,
      lab_flag: fd.get("flag-" + i) || null,
      specimen: fd.get("specimen-" + i) || null,
      method: fd.get("method-" + i) || null,
      excluded: fd.has("exclude-" + i),
      exclusion_reason: fd.get("reason-" + i) || "",
    }));
    const body = {
      clinical_date: fd.get("clinical_date") || null,
      time_precision: fd.get("clinical_date") ? "day" : "unknown",
      patient_match_confirmed: fd.has("match"),
      source_report_status: fd.get("status"),
      document_only: fd.has("document_only"),
      manual_transcription_confirmed: fd.has("manual"),
      source_label: fd.get("source"),
      ...(fd.get("supersedes")
        ? { supersedes_report_id: fd.get("supersedes") }
        : {}),
      results: fd.has("document_only") ? [] : results,
    };
    try {
      const value = object(
        await action.run("/api/v1/labs/reports/" + id + "/review", body, {
          method: "PATCH",
          etag: text(saved?.etag || report.etag),
        }),
      );
      setSaved(value);
      setDirty(false);
      return true;
    } catch {
      return false;
    }
  }
  return (
    <div className="stack">
      <form
        className="form"
        ref={ref}
        onChange={() => {
          setDirty(true);
        }}
        onSubmit={(event) => {
          event.preventDefault();
          void save();
        }}
      >
        <label className="field">
          Reporting laboratory
          <input name="source" defaultValue={text(original.source_label, "")} />
        </label>
        <label className="field">
          Collection date (leave blank if absent)
          <input
            name="clinical_date"
            type="date"
            defaultValue={text(original.clinical_date, "")}
          />
        </label>
        <label className="field">
          Source report status
          <select
            name="status"
            defaultValue={text(original.source_report_status, "unknown")}
          >
            {["unknown", "preliminary", "final", "corrected"].map((v) => (
              <option key={v}>{v}</option>
            ))}
          </select>
        </label>
        <label className="field">
          Corrects an earlier report ID (optional)
          <input
            name="supersedes"
            defaultValue={text(original.supersedes_report_id, "")}
          />
        </label>
        <label className="check">
          <input
            type="checkbox"
            name="match"
            defaultChecked={original.patient_match_confirmed === true}
            required
          />
          I confirmed this report belongs to the intended patient.
        </label>
        <label className="check">
          <input type="checkbox" name="manual" />I explicitly confirmed a manual
          transcription if extraction failed.
        </label>
        <label className="check">
          <input
            type="checkbox"
            name="document_only"
            defaultChecked={original.document_only === true}
          />
          Keep as document only; publish no structured results.
        </label>
        {Array.from({ length: count }, (_, i) => (
          <Card key={i} title={"Result " + (i + 1)}>
            <div className="form">
              <label className="field">
                Test name
                <input
                  name={"label-" + i}
                  defaultValue={text(rows[i]?.label, "")}
                />
              </label>
              <label className="field">
                Exact original result text
                <input
                  name={"raw-" + i}
                  defaultValue={text(rows[i]?.raw_result_text, "")}
                  placeholder="e.g. <5 or Not detected"
                />
              </label>
              <div className="grid2">
                <label className="field">
                  Result kind
                  <select
                    name={"kind-" + i}
                    defaultValue={text(rows[i]?.value_kind, "numeric")}
                  >
                    <option>numeric</option>
                    <option>text</option>
                    <option>coded</option>
                  </select>
                </label>
                <label className="field">
                  Comparison operator
                  <select
                    name={"operator-" + i}
                    defaultValue={text(rows[i]?.operator, "eq")}
                  >
                    {[
                      ["eq", "="],
                      ["lt", "<"],
                      ["le", "≤"],
                      ["gt", ">"],
                      ["ge", "≥"],
                    ].map(([v, t]) => (
                      <option key={v} value={v}>
                        {t}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="field">
                  Numeric value
                  <input
                    name={"value-" + i}
                    inputMode="decimal"
                    defaultValue={text(rows[i]?.value, "")}
                  />
                </label>
                <label className="field">
                  Unit
                  <input
                    name={"unit-" + i}
                    defaultValue={text(rows[i]?.unit, "")}
                  />
                </label>
              </div>
              {[
                ["range", "Reference interval", "reference_text"],
                ["flag", "Original laboratory flag", "lab_flag"],
                ["specimen", "Specimen", "specimen"],
                ["method", "Method", "method"],
              ].map(([key, title, property]) => (
                <label className="field" key={key}>
                  {title}
                  <input
                    name={key + "-" + i}
                    defaultValue={text(rows[i]?.[property], "")}
                  />
                </label>
              ))}
              <label className="check">
                <input name={"exclude-" + i} type="checkbox" />
                Exclude this result
              </label>
              <label className="field">
                Exclusion reason
                <input name={"reason-" + i} />
              </label>
            </div>
          </Card>
        ))}
        <button
          type="button"
          onClick={() => {
            setCount((n) => n + 1);
            setDirty(true);
          }}
        >
          Add result
        </button>
        <ActionFeedback action={action} />
        <button disabled={action.busy}>Save review draft</button>
      </form>
      {saved && !dirty && (
        <button
          className="primary"
          disabled={action.busy}
          onClick={() =>
            void action
              .run(
                "/api/v1/labs/reports/" + id + "/publish",
                {},
                { etag: text(saved.etag) },
              )
              .then(onDone)
              .catch(() => {})
          }
        >
          Publish reviewed results
        </button>
      )}
      <DirtyGuard dirty={dirty} onSave={save} />
    </div>
  );
}
