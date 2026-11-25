import JournalExtras, { SmallRecordEditor } from "../components/JournalExtras";
import { useRef, useState } from "react";
import { usePage } from "../app/Shell";
import {
  records,
  recordSchema,
  useApi,
  type ClinicalRecord,
} from "../api/hooks";
import { api } from "../api/transport";
import {
  ActionFeedback,
  confirmPendingChange,
  Badge,
  Card,
  DirtyGuard,
  Empty,
  ErrorBox,
  LoadState,
  Modal,
  Provenance,
  RevisionConflict,
  Segments,
  useAction,
} from "../components/ui";
import { Timing, timing } from "../components/Timing";
import { dateLabel, label, object, shiftDate, text } from "../lib/display";
export default function Journal() {
  const { date, setDate, readOnly } = usePage();
  const [selected, setSelected] = useState<ClinicalRecord | null>(null),
    [editorKey, setEditorKey] = useState(0),
    [editingQuestion, setEditingQuestion] = useState<ClinicalRecord | null>(
      null,
    ),
    [filter, setFilter] = useState("all"),
    [search, setSearch] = useState(""),
    [results, setResults] = useState<ClinicalRecord[] | null>(null),
    [searchError, setSearchError] = useState<unknown>(null);
  const entries = useApi(
    "/api/v1/journal/entries?from=" +
      shiftDate(date, -365) +
      "&to=" +
      date +
      (filter === "all" ? "" : "&visibility=" + filter),
  );
  const questions = useApi(
    "/api/v1/journal/questions?from=" + date + "&to=" + date,
  );
  const context = useApi("/api/v1/overview?date=" + date);
  const rows = results || records(entries.data?.items);
  const queryQuestions = records(questions.data?.items);
  const body = object(context.data?.body),
    weight = records(body.items).find((r) => r.id === body.representative_id);
  const breathing = object(object(context.data?.breathing).selected_session);
  return (
    <div className="stack">
      {editingQuestion && (
        <Modal title="Edit question" onClose={() => setEditingQuestion(null)}>
          <SmallRecordEditor
            record={editingQuestion}
            kind="question"
            date={date}
            onDone={() => setEditingQuestion(null)}
          />
        </Modal>
      )}
      <div className="row between">
        <p className="muted">
          Private by default. Sharing an entry does not create doctor access.
        </p>
        {!readOnly && (
          <button
            className="primary"
            onClick={() => {
              if (!confirmPendingChange()) return;
              setSelected(null);
              setEditorKey((k) => k + 1);
            }}
          >
            + New entry
          </button>
        )}
      </div>
      <div className="tri">
        <div className="stack">
          <Card title={dateLabel(date).slice(0, 3) + " " + date.slice(0, 4)}>
            <div className="calendar">
              {["S", "M", "T", "W", "T", "F", "S"].map((d, i) => (
                <span className="small muted" key={i}>
                  {d}
                </span>
              ))}
              {Array.from(
                {
                  length: new Date(
                    date.slice(0, 8) + "01T00:00:00Z",
                  ).getUTCDay(),
                },
                (_, i) => (
                  <span key={"pad" + i} aria-hidden="true" />
                ),
              )}
              {Array.from(
                {
                  length: new Date(
                    Number(date.slice(0, 4)),
                    Number(date.slice(5, 7)),
                    0,
                  ).getDate(),
                },
                (_, i) => (
                  <button
                    key={i}
                    className={
                      Number(date.slice(-2)) === i + 1 ? "selected" : ""
                    }
                    aria-label={
                      String(i + 1) +
                      " · Select " +
                      date.slice(0, 8) +
                      String(i + 1).padStart(2, "0")
                    }
                    onClick={() =>
                      setDate(date.slice(0, 8) + String(i + 1).padStart(2, "0"))
                    }
                  >
                    {i + 1}
                  </button>
                ),
              )}
            </div>
          </Card>
          <form
            className="form"
            onSubmit={(event) => {
              event.preventDefault();
              setSearchError(null);
              void api("/api/v1/journal/search", {
                method: "POST",
                body: {
                  query: search,
                  from: shiftDate(date, -365),
                  to: date,
                  ...(filter === "all" ? {} : { visibility: filter }),
                },
              })
                .then((value) => setResults(records(object(value).items)))
                .catch(setSearchError);
            }}
          >
            <label className="field">
              Search entries
              <input
                value={search}
                onChange={(event) => {
                  setSearch(event.target.value);
                  if (!event.target.value) setResults(null);
                }}
                placeholder="Search your journal…"
              />
            </label>
            <button disabled={!search.trim()}>Search</button>
            <ErrorBox error={searchError} />
          </form>
          <Segments
            label="Entry visibility"
            values={["all", "shared", "private"]}
            value={filter}
            onChange={(value) => {
              setFilter(value);
              setResults(null);
            }}
          />
          <LoadState loading={entries.isPending} error={entries.error}>
            <div>
              {rows.map((entry) => (
                <button
                  className={
                    "listButton " +
                    (selected?.id === entry.id ? "selected" : "")
                  }
                  key={entry.id}
                  onClick={() => {
                    if (selected?.id === entry.id || !confirmPendingChange())
                      return;
                    if (entry.kind === "question") {
                      setEditingQuestion(entry);
                      return;
                    }
                    setSelected(entry);
                    setEditorKey((k) => k + 1);
                  }}
                >
                  <div className="row between">
                    <strong>{text(entry.data.title, "Journal entry")}</strong>
                    <Badge>{label(entry.data.visibility)}</Badge>
                  </div>
                  <small>{dateLabel(entry.clinical_date)}</small>
                  <small>{text(entry.data.text, "").slice(0, 110)}</small>
                </button>
              ))}
              {!rows.length && <Empty>No entries in this selection.</Empty>}
            </div>
          </LoadState>
        </div>
        <JournalEditor
          key={String(editorKey) + date}
          record={selected}
          date={date}
          readOnly={readOnly}
          onSaved={(record) => {
            setSelected(record);
            setEditorKey((k) => k + 1);
            void entries.refetch();
          }}
        />
        <div className="stack">
          <Card title="Measurements on this day">
            <LoadState loading={context.isPending} error={context.error}>
              <div className="keyValue">
                <strong>FEV1</strong>
                <span>
                  {text(object(object(breathing.data).values).fev1)} L
                </span>
              </div>
              <div className="keyValue">
                <strong>Morning weight</strong>
                <span>
                  {text(weight?.data.display_value)}{" "}
                  {text(weight?.data.display_unit, "")}
                </span>
              </div>
              <p className="small muted">
                Only authorized recorded measurements are shown.
              </p>
            </LoadState>
          </Card>
          <Card title="Questions for my doctor">
            {queryQuestions.map((question) => (
              <div key={question.id} className="stack">
                <p className="note">{text(question.data.text)}</p>
                <Badge>{label(question.data.visibility)}</Badge>
                {!readOnly && (
                  <button onClick={() => setEditingQuestion(question)}>
                    Edit question
                  </button>
                )}
              </div>
            ))}
            {!queryQuestions.length && <Empty>No saved questions.</Empty>}
            {!readOnly && <QuestionEditor date={date} origin={selected?.id} />}
          </Card>
          {!readOnly && <JournalExtras date={date} />}
          <Card
            title={
              selected?.data.visibility === "shared"
                ? "This entry can be selected for sharing"
                : "This entry is private"
            }
          >
            <p className="muted">
              Only explicitly shared entries inside a doctor's grant appear in
              their view. A question can be shared independently.
            </p>
          </Card>
        </div>
      </div>
    </div>
  );
}
function JournalEditor({
  record,
  date,
  readOnly,
  onSaved,
}: {
  record: ClinicalRecord | null;
  date: string;
  readOnly: boolean;
  onSaved: (r: ClinicalRecord) => void;
}) {
  const ref = useRef<HTMLFormElement>(null),
    action = useAction();
  const [dirty, setDirty] = useState(false),
    [visibility, setVisibility] = useState(
      text(record?.data.visibility, "private"),
    ),
    [share, setShare] = useState(false),
    [shareText, setShareText] = useState(""),
    [feeling, setFeeling] = useState(text(record?.data.feeling, "")),
    [medication, setMedication] = useState(false),
    [etag, setEtag] = useState(record?.etag),
    [current, setCurrent] = useState<ClinicalRecord | null>(null),
    [deleteOpen, setDeleteOpen] = useState(false);
  const meds = useApi(!readOnly ? "/api/v1/journal/medication-events" : null);
  const events = records(meds.data?.items);
  const included = Array.isArray(record?.data.included_medication_ids)
    ? (record.data.included_medication_ids as string[])
    : [];
  async function save() {
    if (!ref.current?.reportValidity()) return false;
    const fd = new FormData(ref.current);
    const selected = fd.getAll("include_medication").map(String);
    const clientId = "new-event";
    const newEvent = medication && String(fd.get("med_name") || "").trim();
    const entry = {
      ...timing(fd),
      title: String(fd.get("title") || ""),
      text: String(fd.get("text") || ""),
      ...(feeling ? { feeling } : {}),
      ...(fd.get("severity") ? { severity: fd.get("severity") } : {}),
    };
    const body = {
      entry,
      visibility,
      included_medication_ids: [...selected, ...(newEvent ? [clientId] : [])],
      expected_link_revisions: Object.fromEntries(
        events
          .filter((e) => selected.includes(e.id))
          .map((e) => [e.id, e.etag]),
      ),
      linked_medication_operations: newEvent
        ? [
            {
              action: "create",
              client_id: clientId,
              data: {
                name: fd.get("med_name"),
                dose: fd.get("med_dose") || null,
                unit: fd.get("med_unit") || null,
                clinical_date: fd.get("med_date"),
                time_precision: "day",
              },
            },
          ]
        : [],
    };
    try {
      const result = recordSchema.parse(
        await action.run(
          "/api/v1/journal/entries" + (record ? "/" + record.id : ""),
          body,
          { method: record ? "PATCH" : "POST", etag },
        ),
      );
      setDirty(false);
      onSaved(result);
      return true;
    } catch {
      if (record)
        try {
          setCurrent(
            recordSchema.parse(
              await api("/api/v1/journal/entries/" + record.id),
            ),
          );
        } catch {
          /* transport clears forbidden state */
        }
      return false;
    }
  }
  if (readOnly)
    return (
      <Card title={text(record?.data.title, "Select an entry")}>
        {record ? (
          <>
            <p className="note">{text(record.data.text)}</p>
            <Provenance record={record} />
          </>
        ) : (
          <Empty>Select a permitted entry to read it.</Empty>
        )}
      </Card>
    );
  return (
    <Card>
      <form
        ref={ref}
        className="form"
        onChange={() => setDirty(true)}
        onSubmit={(e) => {
          e.preventDefault();
          void save();
        }}
      >
        <div className="row between">
          <h2>{record ? "Edit entry" : "New entry"}</h2>
          <Segments
            label="Entry sharing"
            values={["private", "shared"]}
            value={visibility}
            onChange={(v) => {
              setVisibility(v);
              setDirty(true);
              if (v === "shared") {
                setShareText(
                  String(new FormData(ref.current!).get("text") || ""),
                );
                setShare(true);
              }
            }}
          />
        </div>
        <label className="field">
          Title (optional)
          <input
            name="title"
            maxLength={256}
            defaultValue={text(record?.data.title, "")}
            placeholder="Daily check-in"
          />
        </label>
        <Timing date={record?.clinical_date || date} />
        <div>
          <h3>How are you feeling?</h3>
          <Segments
            label="Self-reported feeling"
            values={["very_low", "low", "okay", "good", "very_good"]}
            value={feeling}
            onChange={(v) => {
              setFeeling(v);
              setDirty(true);
            }}
          />
          <button
            type="button"
            className="quiet"
            onClick={() => {
              setFeeling("");
              setDirty(true);
            }}
          >
            Not recorded
          </button>
        </div>
        <label className="field">
          Self-reported symptom severity
          <select
            name="severity"
            defaultValue={text(record?.data.severity, "")}
          >
            <option value="">Not recorded</option>
            {["none", "mild", "moderate", "severe"].map((v) => (
              <option key={v} value={v}>
                {label(v)}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          Entry
          <textarea
            name="text"
            rows={8}
            defaultValue={text(record?.data.text, "")}
            placeholder="What would you like to remember?"
          />
        </label>
        <h3>Medication events</h3>
        {events.map((event) => (
          <label className="check" key={event.id}>
            <input
              type="checkbox"
              name="include_medication"
              value={event.id}
              defaultChecked={included.includes(event.id)}
            />
            {text(event.data.name)} · {dateLabel(event.clinical_date)}
          </label>
        ))}
        {!events.length && !medication && (
          <Empty>
            No events recorded. This does not mean no medicine was taken.
          </Empty>
        )}
        <button
          type="button"
          className="quiet danger"
          onClick={() => {
            setMedication(!medication);
            setDirty(true);
          }}
        >
          {medication ? "Remove new event" : "+ Add event"}
        </button>
        {medication && (
          <div className="form">
            <label className="field">
              Medication name
              <input name="med_name" required />
            </label>
            <div className="grid2">
              <label className="field">
                Dose (optional)
                <input name="med_dose" inputMode="decimal" />
              </label>
              <label className="field">
                Unit
                <input name="med_unit" />
              </label>
            </div>
            <label className="field">
              Event date
              <input name="med_date" type="date" defaultValue={date} required />
            </label>
            <p className="small muted">
              An omitted dose is recorded as not supplied. New events are saved
              atomically with this entry.
            </p>
          </div>
        )}
        <ActionFeedback action={action} />
        <RevisionConflict
          error={action.error}
          current={<p className="note">{text(current?.data.text)}</p>}
          local={<p>Your text remains in the editor above.</p>}
          onReload={() => {
            setEtag(current?.etag);
            action.setError(null);
          }}
        />
        <button className="primary" disabled={action.busy || !dirty}>
          {action.busy ? "Saving…" : "Save entry"}
        </button>
        {record && (
          <button
            type="button"
            className="danger"
            onClick={() => setDeleteOpen(true)}
          >
            Delete entry
          </button>
        )}
      </form>
      <DirtyGuard dirty={dirty} onSave={save} />
      {share && (
        <Modal
          title="Share this entry?"
          onClose={() => {
            setShare(false);
            setVisibility("private");
          }}
        >
          <p>
            The entry and specifically included medication events may appear
            only inside an authorized doctor grant. This does not invite a
            doctor.
          </p>
          <p className="note">{shareText}</p>
          <div className="dialogActions">
            <button
              onClick={() => {
                setShare(false);
                setVisibility("private");
              }}
            >
              Keep private
            </button>
            <button
              className="primary"
              onClick={() => {
                setShare(false);
                setVisibility("shared");
                setDirty(true);
              }}
            >
              Use shared visibility
            </button>
          </div>
        </Modal>
      )}
      {deleteOpen && record && (
        <Modal title="Delete this entry?" onClose={() => setDeleteOpen(false)}>
          <p>
            Independent medication events will be retained. The entry becomes
            inaccessible immediately.
          </p>
          <button
            className="primary"
            onClick={() =>
              void action
                .run(
                  "/api/v1/journal/entries/" + record.id,
                  {},
                  { method: "DELETE", etag: record.etag },
                )
                .then(() => {
                  setDirty(false);
                  setDeleteOpen(false);
                  location.reload();
                })
                .catch(() => {})
            }
          >
            Delete entry
          </button>
        </Modal>
      )}
    </Card>
  );
}
function QuestionEditor({ date, origin }: { date: string; origin?: string }) {
  const action = useAction(),
    ref = useRef<HTMLFormElement>(null);
  return (
    <form
      ref={ref}
      className="form"
      style={{ marginTop: 16 }}
      onSubmit={(e) => {
        e.preventDefault();
        const fd = new FormData(e.currentTarget);
        void action
          .run("/api/v1/journal/questions", {
            text: fd.get("text"),
            clinical_date: date,
            time_precision: "day",
            visibility: fd.has("shared") ? "shared" : "private",
            ...(origin ? { origin_record_id: origin } : {}),
          })
          .then(() => ref.current?.reset())
          .catch(() => {});
      }}
    >
      <label className="field">
        New question
        <textarea name="text" required />
      </label>
      <label className="check">
        <input type="checkbox" name="shared" />
        Share this question only; the entry remains private
      </label>
      <button disabled={action.busy}>Save question</button>
      <ActionFeedback action={action} />
    </form>
  );
}
