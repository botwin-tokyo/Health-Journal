import PhoneRecords from "../components/PhoneRecords";
import { lazy, Suspense, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { usePage } from "../app/Shell";
import { records, useApi, type ClinicalRecord } from "../api/hooks";
import { api } from "../api/transport";
import {
  ActionFeedback,
  Badge,
  Card,
  DirtyGuard,
  Empty,
  LoadState,
  Metric,
  Modal,
  Provenance,
  RevisionConflict,
  Segments,
  useAction,
} from "../components/ui";
import { Timing, timing } from "../components/Timing";
import {
  dateLabel,
  decimal,
  label,
  list,
  object,
  shiftDate,
  text,
} from "../lib/display";
import BaselineEditor from "../components/BaselineEditor";
import ExportPanel from "../components/ExportPanel";
const Chart = lazy(() => import("../components/ChartFrame"));
const schema = z.object({
  value: z
    .string()
    .regex(/^\d+(\.\d+)?$/, "Enter a decimal number.")
    .refine((v) => Number(v) > 0, "Enter a value greater than zero."),
  unit: z.enum(["lb", "kg"]),
  note: z.string().max(16384),
});
function reading(value: unknown) {
  const number = decimal(value);
  return number === null ? text(value) : new Intl.NumberFormat("en-US", {maximumFractionDigits: 2}).format(number);
}
export default function Body() {
  const { date, range, setRange, readOnly } = usePage();
  const [unit, setUnit] = useState("lb"),
    [edit, setEdit] = useState<ClinicalRecord | null>(null),
    [showExport, setShowExport] = useState(false),
    [showReferences, setShowReferences] = useState(false),
    [baselineId, setBaselineId] = useState("");
  const baselines = useApi("/api/v1/baselines?weight_unit=" + unit);
  const query = useApi(
    `/api/v1/body?date=${date}&from=${shiftDate(date, 1 - range)}&to=${date}&weight_unit=${unit}${baselineId ? "&baseline_id=" + baselineId : ""}`,
    15000,
  );
  const data = query.data || {},
    items = records(data.items),
    chosen = items.find((r) => r.id === data.representative_id) || records(data.representative_record ? [data.representative_record] : [])[0],
    mean = object(data.seven_day_mean),
    reference = baselineId
      ? object(
          records(baselines.data?.items).find((r) => r.id === baselineId)?.data,
        )
      : object(data.recent_baseline),
    delta = object(data.delta);
  return (
    <div className="stack">
      <div className="row between">
        <Segments
          label="Weight units"
          values={["lb", "kg"]}
          value={unit}
          onChange={setUnit}
        />
        <div className="row">
          <label className="field">
            Reference
            <select
              value={baselineId}
              onChange={(e) => setBaselineId(e.target.value)}
            >
              <option value="">Recent personal reference</option>
              {records(baselines.data?.items)
                .filter((r) => r.data.metric_id === "weight")
                .map((r) => (
                  <option key={r.id} value={r.id}>
                    Fixed · {text(r.data.from_date)} – {text(r.data.to_date)}
                  </option>
                ))}
            </select>
          </label>
          <Segments
            label="History range"
            values={["7", "28", "90", "365"]}
            value={String(range)}
            onChange={(v) => setRange(Number(v))}
          />
          {!readOnly && (
            <>
              <button onClick={() => setShowReferences(true)}>
                Personal references
              </button>
              <button onClick={() => setShowExport(true)}>Export</button>
            </>
          )}
        </div>
      </div>
      <LoadState loading={query.isPending} error={query.error}>
        <div className="metrics">
          <Metric
            title="Daily weight"
            value={chosen ? reading(chosen.data.display_value) : undefined}
            unit={unit}
            note={
              chosen ? (
                <>
                  {dateLabel(chosen.clinical_date)} ·{" "}
                  {label(chosen.data.source_type)}
                </>
              ) : (
                "No morning reading selected"
              )
            }
            hero
          />
          <Metric
            title="7-day average"
            value={mean.display_value}
            unit={unit}
            note={`${text(mean.contributor_day_count, "0")} contributing days`}
          />
          <Metric
            title="Recent personal reference"
            value={reference.display_value}
            unit={unit}
            note={label(reference.absent_reason || reference.method_version)}
          />
          <Metric
            title="Change"
            value={delta.display_value}
            unit={unit}
            note={label(delta.absent_reason || "Compared with reference")}
          />
        </div>
        <div className="split">
          <div className="stack">
            <Suspense fallback={<div className="skeleton" />}>
              <Chart
                title="Weight history"
                unit={unit}
                source="Recorded observations · original revisions retained"
                points={items.map((r) => ({
                  x: r.clinical_date || "",
                  value: decimal(r.data.display_value),
                  original: text(r.data.display_value),
                  revision: r.revision_id,
                }))}
              />
            </Suspense>
            <Card title="Recent measurements">
              {items.length ? (
                <div className="tableWrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Date</th>
                        <th>Weight</th>
                        <th>Source</th>
                        <th>Details</th>
                      </tr>
                    </thead>
                    <tbody>
                      {items.map((r) => (
                        <tr key={r.id}>
                          <td>
                            {dateLabel(r.clinical_date)}
                            {r.id === data.representative_id && (
                              <div>
                                <Badge>Daily representative</Badge>
                              </div>
                            )}
                          </td>
                          <td>
                            <strong>
                              {text(r.data.display_value)} {unit}
                            </strong>
                          </td>
                          <td>
                            <Badge>{label(r.data.source_type)}</Badge>
                          </td>
                          <td>
                            <button
                              className="quiet"
                              onClick={() => setEdit(r)}
                            >
                              Open
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <Empty>Record your first morning measurement.</Empty>
              )}
              {!!data.cursor && (
                <a href="#record-date">
                  Narrow the date range to inspect additional measurements.
                </a>
              )}
            </Card>
          </div>
          {!readOnly && (
            <div className="stack formFirst">
              <WeightEditor
                key={date}
                date={date}
                representative={text(data.representative_etag, "")}
                occupied={!!data.representative_id}
                onSaved={() => void query.refetch()}
              />
              <Card title="Scale integration">
                <div className="row">
                  <strong>Body composition scale</strong>
                  <Badge>{chosen?.data.source_type === "direct_scale" ? "Receiving readings" : "Phone sync"}</Badge>
                </div>
                <p className="muted small">
                  Scale readings sent by your phone populate weight and composition automatically.
                </p>
              </Card>
            </div>
          )}
        </div>
        <Card title="Body composition">
          <p className="muted">
            Estimates appear only when qualified source data is available.
          </p>
          <div className="metrics" style={{ marginTop: 20 }}>
            {list(data.composition).map((item) => {
              const row = object(item);
              return (
                <div key={text(row.key)} className="card">
                  <h3>{text(row.label, label(row.key))}</h3>
                  <div className="value">{reading(row.display_value)}{row.display_value != null && <span className="small"> {text(row.display_unit, "")}</span>}</div>
                  <p className="small muted">{row.value == null ? "No reading for this date" : row.estimated ? "Reported estimate" : "Recorded measurement"}</p>
                  {row.value != null && <p className="small muted">{label(row.source_type)}</p>}
                </div>
              );
            })}
          </div>
          <p className="small muted">
            Bone mass is not bone density. Protein percentage is not food
            intake. BMR is an estimate, not daily energy balance.
          </p>
        </Card>
        <PhoneRecords date={date} domain="body" />
      </LoadState>
      {edit && (
        <Modal title="Measurement details" onClose={() => setEdit(null)}>
          <Provenance record={edit} />
          {!readOnly && (
            <WeightEditor
              date={edit.clinical_date || date}
              record={edit}
              representative={text(data.representative_etag, "")}
              occupied={false}
              onSaved={() => {
                setEdit(null);
                void query.refetch();
              }}
            />
          )}
        </Modal>
      )}
      {showReferences && (
        <Modal
          title="Weight references"
          onClose={() => setShowReferences(false)}
        >
          <BaselineEditor metric="weight" />
        </Modal>
      )}
      {showExport && (
        <Modal
          title="Export weight history"
          onClose={() => setShowExport(false)}
        >
          <ExportPanel
            body={{
              format: "body_csv",
              from: shiftDate(date, 1 - range),
              to: date,
            }}
          />
        </Modal>
      )}
    </div>
  );
}
function WeightEditor({
  date,
  representative,
  occupied,
  record,
  onSaved,
}: {
  date: string;
  representative: string;
  occupied: boolean;
  record?: ClinicalRecord;
  onSaved: () => void;
}) {
  const action = useAction(),
    formRef = useRef<HTMLFormElement>(null);
  const [etag, setEtag] = useState(record?.etag),
    [current, setCurrent] = useState<unknown>(null);
  const form = useForm({
    resolver: zodResolver(schema),
    defaultValues: {
      value: text(record?.data.value, ""),
      unit: (record?.data.unit === "kg" ? "kg" : "lb") as "kg" | "lb",
      note: "",
    },
  });
  const [dirty, setDirty] = useState(false),
    [deleting, setDeleting] = useState(false);
  async function save() {
    if (!(await form.trigger())) return false;
    const fd = new FormData(formRef.current!);
    const values = form.getValues();
    const body = {
      ...timing(fd),
      value: values.value,
      unit: values.unit,
      ...(record
        ? {
            representative_action:
              fd.get("representative_action") || "keep_corrected",
          }
        : {
            designation: {
              action: fd.has("designate")
                ? "make_representative"
                : "leave_unchanged",
              expected_etag: representative,
              confirm_replacement: fd.has("replace"),
            },
          }),
      ...(!record && values.note.trim()
        ? { note_operation: { text: values.note, visibility: "private" } }
        : {}),
    };
    try {
      await action.run(
        "/api/v1/body/weights" + (record ? "/" + record.id : ""),
        body,
        { method: record ? "PATCH" : "POST", etag },
      );
      form.reset();
      setDirty(false);
      onSaved();
      return true;
    } catch {
      if (record)
        try {
          setCurrent(await api("/api/v1/body/weights/" + record.id));
        } catch {
          /* authorization is handled by transport */
        }
      return false;
    }
  }
  return (
    <Card title={record ? "Correct measurement" : "Morning check-in"}>
      <form
        ref={formRef}
        className="form"
        onChange={() => setDirty(true)}
        onSubmit={(e) => {
          e.preventDefault();
          void save();
        }}
      >
        <Timing date={date} lockDate initial={record?.data} />
        <div className="grid2">
          <label className="field">
            Weight
            <input
              inputMode="decimal"
              {...form.register("value")}
              aria-invalid={!!form.formState.errors.value}
            />
            {form.formState.errors.value && (
              <span role="alert" className="small danger">
                {form.formState.errors.value.message}
              </span>
            )}
          </label>
          <label className="field">
            Unit
            <select {...form.register("unit")}>
              <option>lb</option>
              <option>kg</option>
            </select>
          </label>
        </div>
        {record ? (
          <label className="field">
            Morning designation after correction
            <select name="representative_action">
              <option value="keep_corrected">Keep this reading selected</option>
              <option value="clear">Clear its morning designation</option>
            </select>
          </label>
        ) : (
          <>
            <label className="check">
              <input type="checkbox" name="designate" defaultChecked />
              Use as this day's morning reading
            </label>
            {occupied && (
              <label className="check">
                <input name="replace" type="checkbox" />
                Replace the existing morning selection
              </label>
            )}
            <label className="field">
              Private note (optional)
              <textarea
                {...form.register("note")}
                placeholder="Add context for this reading…"
              />
            </label>
          </>
        )}
        <ActionFeedback action={action} />
        <RevisionConflict
          error={action.error}
          current={
            <p>
              {text(object(object(current).data).value)}{" "}
              {text(object(object(current).data).unit)}
            </p>
          }
          local={
            <p>
              {form.getValues("value")} {form.getValues("unit")}
            </p>
          }
          onReload={() => {
            setEtag(text(object(current).etag));
            action.setError(null);
          }}
        />
        <button
          className="primary full"
          disabled={action.busy || (!dirty && !!record)}
        >
          {action.busy
            ? "Saving…"
            : record
              ? "Save correction"
              : "Save reading"}
        </button>
        {record && (
          <button
            type="button"
            className="danger"
            onClick={() => setDeleting(true)}
          >
            Delete this reading
          </button>
        )}
      </form>
      <DirtyGuard dirty={dirty} onSave={save} />
      {deleting && record && (
        <Modal title="Delete this reading?" onClose={() => setDeleting(false)}>
          <p>
            The reading becomes inaccessible and its morning designation is
            cleared. Another reading will not be selected automatically.
          </p>
          <button
            className="primary"
            onClick={() =>
              void action
                .run(
                  "/api/v1/body/weights/" + record.id,
                  {},
                  { method: "DELETE", etag: record.etag },
                )
                .then(() => {
                  setDirty(false);
                  onSaved();
                })
                .catch(() => {})
            }
          >
            Delete reading
          </button>
        </Modal>
      )}
    </Card>
  );
}
