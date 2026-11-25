import { useState } from "react";
import { usePage } from "../app/Shell";
import {
  records,
  recordSchema,
  useApi,
  useSession,
  type ClinicalRecord,
} from "../api/hooks";
import { preview, switchContext } from "../api/transport";
import {
  ActionFeedback,
  Badge,
  Card,
  Empty,
  LoadState,
  Modal,
  useAction,
} from "../components/ui";
import ExportPanel from "../components/ExportPanel";
import {
  dateLabel,
  label,
  list,
  object,
  shiftDate,
  text,
} from "../lib/display";
const categories = [
  "body",
  "breathing",
  "sleep_activity",
  "labs",
  "journal",
  "questions",
];
export function GrantChooser() {
  const grants = useApi("/api/v1/sharing/grants"),
    action = useAction();
  return (
    <Card title="Choose a shared journal">
      <p>Your access is limited to each owner's approved scope.</p>
      {list(grants.data?.items)
        .map(object)
        .filter((g) => g.state === "active")
        .map((g) => (
          <button
            className="listButton"
            key={text(g.id)}
            onClick={() =>
              void switchContext(text(g.id)).catch(action.setError)
            }
          >
            Open shared journal · {dateLabel(text(g.starts_on))}–
            {dateLabel(text(g.ends_on))}
          </button>
        ))}
      <ActionFeedback action={action} />
    </Card>
  );
}
export default function Review() {
  const { date, readOnly } = usePage(),
    { session } = useSession();
  const [from, setFrom] = useState(shiftDate(date, -27)),
    [to, setTo] = useState(date),
    [title, setTitle] = useState("Health review"),
    [selection, setSelection] = useState<string[]>([]),
    [appendices, setAppendices] = useState<string[]>([]),
    [audience, setAudience] = useState(""),
    [draft, setDraft] = useState<ClinicalRecord | null>(null),
    [snapshot, setSnapshot] = useState<ClinicalRecord | null>(null),
    [exportOpen, setExportOpen] = useState(false),
    [manage, setManage] = useState<Record<string, unknown> | null>(null);
  const action = useAction();
  const body = useApi(
      "/api/v1/body?date=" +
        date +
        "&from=" +
        from +
        "&to=" +
        to +
        "&weight_unit=lb",
    ),
    breathing = useApi("/api/v1/breathing?date=" + date),
    sleep = useApi("/api/v1/sleep-activity?date=" + date),
    journal = useApi(
      "/api/v1/journal/entries?from=" +
        from +
        "&to=" +
        to +
        "&visibility=shared",
    ),
    questions = useApi(
      "/api/v1/journal/questions?from=" +
        from +
        "&to=" +
        to +
        "&visibility=shared",
    ),
    labs = useApi("/api/v1/labs/trends?from=" + from + "&to=" + to),
    grants = useApi(!readOnly ? "/api/v1/sharing/grants" : null),
    documents = useApi(!readOnly ? "/api/v1/labs/reports" : null),
    medication = useApi(!readOnly ? "/api/v1/journal/medication-events" : null);
  const recordsForReview = [
    ...records(body.data?.items),
    ...records(breathing.data?.items),
    ...records(sleep.data?.sleep_sessions),
    ...records(sleep.data?.workouts),
    ...records(journal.data?.items),
    ...records(questions.data?.items),
    ...list(labs.data?.series).flatMap((s) => records(object(s).points)),
  ];
  const unique = [...new Map(recordsForReview.map((r) => [r.id, r])).values()];
  const groups = categories.map((category) => ({
    category,
    items: unique.filter(
      (r) =>
        (
          ({
            weight: "body",
            pulmonary: "breathing",
            sleep: "sleep_activity",
            workout: "sleep_activity",
            lab: "labs",
            journal: "journal",
            question: "questions",
          }) as Record<string, string>
        )[r.kind] === category,
    ),
  }));
  async function freeze() {
    try {
      const body = {
        title,
        clinical_date: date,
        time_precision: "day",
        from,
        to,
        record_ids: selection,
        document_ids: appendices,
        weight_unit: "lb",
        ...(audience ? { grant_id: audience } : {}),
      };
      const saved = recordSchema.parse(
        await action.run(
          "/api/v1/review/drafts" + (draft ? "/" + draft.id : ""),
          body,
          { method: draft ? "PATCH" : "POST", etag: draft?.etag },
        ),
      );
      setDraft(saved);
      const frozen = recordSchema.parse(
        await action.run(
          "/api/v1/review/drafts/" + saved.id + "/snapshots",
          {},
          { etag: saved.etag },
        ),
      );
      setSnapshot(frozen);
    } catch {
      /* feedback preserves selection */
    }
  }
  return (
    <div className="stack">
      <div className="card row between">
        <div className="row">
          <label className="field">
            From
            <input
              type="date"
              value={from}
              onChange={(e) => setFrom(e.target.value)}
            />
          </label>
          <label className="field">
            To
            <input
              type="date"
              value={to}
              onChange={(e) => setTo(e.target.value)}
            />
          </label>
        </div>
        <label className="field">
          Report title
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            maxLength={256}
          />
        </label>
        {!readOnly && (
          <button
            className="primary"
            disabled={action.busy || !selection.length}
            onClick={() => void freeze()}
          >
            Freeze report preview
          </button>
        )}
      </div>
      <ActionFeedback action={action} />
      <div className="tri">
        <div className="stack">
          <Card title="Include in report">
            {groups.map((group) => (
              <details open key={group.category}>
                <summary>{label(group.category)}</summary>
                {group.items.map((r) => (
                  <label className="check" key={r.id}>
                    <input
                      type="checkbox"
                      disabled={readOnly}
                      checked={selection.includes(r.id)}
                      onChange={(e) => {
                        setSelection((ids) =>
                          e.target.checked
                            ? [...ids, r.id]
                            : ids.filter((id) => id !== r.id),
                        );
                      }}
                    />
                    {r.kind === "question" || r.kind === "journal"
                      ? text(r.data.title || r.data.text).slice(0, 80)
                      : label(r.kind) + " · " + dateLabel(r.clinical_date)}
                  </label>
                ))}
                {!group.items.length && (
                  <p className="small muted">
                    No available records in this selection.
                  </p>
                )}
              </details>
            ))}
            {!readOnly && (
              <details>
                <summary>Original PDF appendices</summary>
                <p className="small muted">
                  Including an original PDF includes the whole document and
                  requires separate permission for the chosen audience.
                </p>
                {list(documents.data?.items)
                  .map(object)
                  .filter((d) => d.parse_state === "ready")
                  .map((d) => (
                    <label className="check" key={text(d.id)}>
                      <input
                        type="checkbox"
                        checked={appendices.includes(text(d.document_id))}
                        onChange={(e) =>
                          setAppendices((ids) =>
                            e.target.checked
                              ? [...ids, text(d.document_id)]
                              : ids.filter((id) => id !== d.document_id),
                          )
                        }
                      />
                      Original report · {text(d.id)}
                    </label>
                  ))}
              </details>
            )}
            <div className="notice small">
              🔒 Private journal entries are excluded.
            </div>
          </Card>
          <Card title="Questions for this visit">
            {records(questions.data?.items).map((r) => (
              <p key={r.id} className="note">
                {text(r.data.text)}
              </p>
            ))}
            {!records(questions.data?.items).length && (
              <Empty>Save a question in Journal before including it.</Empty>
            )}
          </Card>
        </div>
        <Card title="Personal health summary">
          {snapshot ? (
            <>
              <div className="row between">
                <h2>{text(snapshot.data.title)}</h2>
                <Badge>Frozen snapshot</Badge>
              </div>
              <p className="small muted">
                {dateLabel(text(object(snapshot.data.selection).from, ""))}–
                {dateLabel(text(object(snapshot.data.selection).to, ""))}
              </p>
              <div className="stack" style={{ marginTop: 20 }}>
                {list(snapshot.data.sections).map((value, index) => {
                  const section = object(value),
                    data = object(section.data);
                  return (
                    <section key={index}>
                      <h3>
                        {label(section.heading)} ·{" "}
                        {dateLabel(text(section.clinical_date, ""))}
                      </h3>
                      <div className="row">
                        <strong>
                          {text(
                            data.display_value ||
                              data.raw_result_text ||
                              data.value ||
                              object(data.values).fev1,
                            "",
                          )}
                        </strong>
                        <span>{text(data.display_unit || data.unit, "")}</span>
                        <Badge>{label(data.source_type)}</Badge>
                      </div>
                      {!!data.text && <p className="note">{text(data.text)}</p>}
                      <details>
                        <summary>
                          Saved values, source and qualifications
                        </summary>
                        <SnapshotValues value={data} />
                      </details>
                      <p className="mono muted">
                        Revision {text(section.revision_id)}
                      </p>
                    </section>
                  );
                })}
              </div>
              <p className="notice small" style={{ marginTop: 20 }}>
                A later sync cannot change this snapshot. Freeze a new preview
                to include changed records.
              </p>
              {!readOnly && (
                <button className="primary" onClick={() => setExportOpen(true)}>
                  Prepare PDF from this snapshot
                </button>
              )}
            </>
          ) : (
            <Empty>
              {readOnly
                ? "Review only the records permitted by this grant. No owner drafting controls are available."
                : "Select records and freeze the preview. The PDF will use those exact revisions."}
            </Empty>
          )}
        </Card>
        <div className="stack">
          <Card title="Doctor access">
            {readOnly ? (
              <>
                <Badge>Read-only</Badge>
                <p>Review access is not continuous monitoring.</p>
                <p className="small muted">
                  Context:{" "}
                  {session?.context.view_mode === "owner_preview"
                    ? "Owner preview"
                    : "Doctor"}
                </p>
              </>
            ) : (
              <>
                <label className="field">
                  Report audience
                  <select
                    value={audience}
                    onChange={(e) => setAudience(e.target.value)}
                  >
                    <option value="">Owner appointment copy</option>
                    {list(grants.data?.items)
                      .map(object)
                      .filter((g) => g.state === "active")
                      .map((g) => (
                        <option key={text(g.id)} value={text(g.id)}>
                          {text(g.recipient_email)}
                        </option>
                      ))}
                  </select>
                </label>
                <LoadState loading={grants.isPending} error={grants.error}>
                  {list(grants.data?.items)
                    .map(object)
                    .map((g) => (
                      <div key={text(g.id)} style={{ marginTop: 20 }}>
                        <strong>{text(g.recipient_email)}</strong>
                        <div>
                          <Badge>{label(g.state)}</Badge>
                        </div>
                        <p className="small muted">
                          {dateLabel(text(g.starts_on))}–
                          {dateLabel(text(g.ends_on))}
                          <br />
                          Expires {text(g.expires_at)}
                        </p>
                        <div className="row">
                          <button onClick={() => setManage(g)}>
                            Manage access
                          </button>
                          {g.state === "active" && (
                            <button
                              onClick={() =>
                                void preview(text(g.id)).catch(action.setError)
                              }
                            >
                              Preview shared view
                            </button>
                          )}
                        </div>
                      </div>
                    ))}
                </LoadState>
                <button
                  className="primary"
                  style={{ marginTop: 20 }}
                  onClick={() => setManage({})}
                >
                  Create scoped access
                </button>
              </>
            )}
          </Card>
          <Card title="Sharing control" className="hero">
            <p>Private entries stay excluded.</p>
            <p className="small">
              Reading, downloading a report and opening an original PDF are
              separate permissions.
            </p>
          </Card>
        </div>
      </div>
      {manage && (
        <Modal
          title={
            manage.id ? "Manage doctor access" : "Create scoped doctor access"
          }
          onClose={() => setManage(null)}
        >
          <GrantEditor
            grant={manage}
            from={from}
            to={to}
            records={[...unique, ...records(medication.data?.items)]}
            documents={list(documents.data?.items).map(object)}
            onDone={() => setManage(null)}
          />
        </Modal>
      )}
      {exportOpen && snapshot && (
        <Modal
          title="Prepare appointment PDF"
          onClose={() => setExportOpen(false)}
        >
          <ExportPanel
            path={"/api/v1/review/snapshots/" + snapshot.id + "/exports"}
            etag={snapshot.etag}
            body={{}}
          />
        </Modal>
      )}
    </div>
  );
}
function GrantEditor({
  grant,
  from,
  to,
  records: rows,
  documents,
  onDone,
}: {
  grant: Record<string, unknown>;
  from: string;
  to: string;
  records: ClinicalRecord[];
  documents: Record<string, unknown>[];
  onDone: () => void;
}) {
  const action = useAction();
  const [created, setCreated] = useState<Record<string, unknown> | null>(null),
    [confirmRevoke, setConfirmRevoke] = useState(false);
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const fd = new FormData(event.currentTarget);
    const cats = fd.getAll("category").map(String),
      actions = fd.getAll("action").map(String),
      selected = (kind: string) =>
        rows
          .filter((r) => r.kind === kind && fd.has("record-" + r.id))
          .map((r) => r.id);
    const lists = {
      journal: selected("journal"),
      questions: selected("question"),
      labs: selected("lab"),
      medication_events: selected("medication"),
    };
    const body = grant.id
      ? {
          starts_on: fd.get("from"),
          ends_on: fd.get("to"),
          expires_at: new Date(String(fd.get("expiry"))).toISOString(),
          categories: cats,
          actions,
          selected_entry_ids: lists.journal,
          selected_question_ids: lists.questions,
          selected_result_ids: lists.labs,
          whole_document_ids: fd.getAll("document").map(String),
          selected_medication_event_ids: lists.medication_events,
        }
      : {
          recipient_email: fd.get("email"),
          from: fd.get("from"),
          to: fd.get("to"),
          categories: cats,
          actions,
          record_allowlists: lists,
          document_ids: fd.getAll("document").map(String),
        };
    try {
      const value = object(
        await action.run(
          "/api/v1/sharing/grants" + (grant.id ? "/" + grant.id : ""),
          body,
          {
            method: grant.id ? "PATCH" : "POST",
            etag: grant.id ? text(grant.etag) : undefined,
          },
        ),
      );
      setCreated(value);
      if (grant.id) onDone();
    } catch {
      /* keep form */
    }
  }
  return (
    <div className="stack">
      <form className="form" onSubmit={(event) => void submit(event)}>
        <label className="field">
          Doctor email
          <input
            type="email"
            name="email"
            defaultValue={text(grant.recipient_email, "")}
            required
            disabled={!!grant.id}
          />
        </label>
        <div className="grid2">
          <label className="field">
            From
            <input
              name="from"
              type="date"
              defaultValue={text(grant.starts_on, from)}
              required
            />
          </label>
          <label className="field">
            To
            <input
              name="to"
              type="date"
              defaultValue={text(grant.ends_on, to)}
              required
            />
          </label>
        </div>
        {!!grant.id && (
          <label className="field">
            Expiry
            <input
              name="expiry"
              type="datetime-local"
              defaultValue={text(grant.expires_at).slice(0, 16)}
              required
            />
          </label>
        )}
        <fieldset>
          <legend>Permitted categories</legend>
          {categories.map((c) => (
            <label className="check" key={c}>
              <input
                type="checkbox"
                name="category"
                value={c}
                defaultChecked={list(grant.categories).includes(c)}
              />
              {label(c)}
            </label>
          ))}
        </fieldset>
        <fieldset>
          <legend>Actions</legend>
          {["read", "download_report", "read_original_document"].map((a) => (
            <label className="check" key={a}>
              <input
                type="checkbox"
                name="action"
                value={a}
                defaultChecked={
                  list(grant.actions).includes(a) || (!grant.id && a === "read")
                }
              />
              {label(a)}
            </label>
          ))}
        </fieldset>
        <p className="small muted">
          Original PDF access exposes the whole document, including unselected
          results and personal details. Select documents explicitly below. Named
          entries, questions and lab results require individual selection below.
          Expanding an active grant requires a new grant.
        </p>
        {rows
          .filter(
            (r) =>
              ["journal", "question", "lab", "medication"].includes(r.kind) &&
              r.data.visibility !== "private",
          )
          .map((r) => (
            <label className="check" key={r.id}>
              <input
                type="checkbox"
                name={"record-" + r.id}
                defaultChecked={[
                  ...list(grant.selected_entry_ids),
                  ...list(grant.selected_question_ids),
                  ...list(grant.selected_result_ids),
                  ...list(grant.selected_medication_event_ids),
                ].includes(r.id)}
              />
              {label(r.kind)} ·{" "}
              {text(r.data.title || r.data.label || r.data.text).slice(0, 100)}
            </label>
          ))}
        <fieldset>
          <legend>Whole original documents</legend>
          {documents
            .filter((d) => d.document_id)
            .map((d) => (
              <label className="check" key={text(d.id)}>
                <input
                  name="document"
                  value={text(d.document_id)}
                  type="checkbox"
                  defaultChecked={list(grant.whole_document_ids).includes(
                    d.document_id,
                  )}
                />
                I permit the entire original document ·{" "}
                {text(d.source_label || d.id)}
              </label>
            ))}
        </fieldset>
        <ActionFeedback action={action} />
        <button className="primary" disabled={action.busy}>
          {grant.id ? "Save narrowed scope" : "Save draft grant"}
        </button>
      </form>
      {!!created?.id && (
        <p className="notice">
          Draft saved. It does not grant active access. Invitation delivery and
          recipient acceptance are separate steps.
        </p>
      )}
      {(grant.state === "draft" || !!created?.id) && (
        <button
          disabled={action.busy}
          onClick={() =>
            void action
              .run(
                "/api/v1/sharing/grants/" +
                  text(created?.id || grant.id) +
                  "/invite",
                {},
                { etag: text(created?.etag || grant.etag) },
              )
              .then(() =>
                action.setMessage(
                  "Invitation prepared. Local development does not deliver external email.",
                ),
              )
              .catch(() => {})
          }
        >
          Prepare named invitation
        </button>
      )}
      {!!grant.id && grant.state !== "revoked" && (
        <button className="danger" onClick={() => setConfirmRevoke(true)}>
          Revoke access
        </button>
      )}
      {confirmRevoke && (
        <Modal
          title="Revoke doctor access?"
          onClose={() => setConfirmRevoke(false)}
        >
          <p>
            New reads and downloads will stop. Already downloaded copies cannot
            be recalled.
          </p>
          <button
            className="primary"
            onClick={() =>
              void action
                .run("/api/v1/sharing/grants/" + text(grant.id) + "/revoke", {})
                .then(onDone)
                .catch(() => {})
            }
          >
            Revoke access now
          </button>
        </Modal>
      )}
    </div>
  );
}

function SnapshotValues({ value }: { value: unknown }) {
  if (value === null || value === undefined) return <span>Not recorded</span>;
  if (Array.isArray(value))
    return (
      <ol>
        {value.map((v, i) => (
          <li key={i}>
            <SnapshotValues value={v} />
          </li>
        ))}
      </ol>
    );
  if (typeof value === "object")
    return (
      <dl className="provenance">
        {Object.entries(value).map(([key, v]) => (
          <div key={key}>
            <dt>{label(key)}</dt>
            <dd>
              <SnapshotValues value={v} />
            </dd>
          </div>
        ))}
      </dl>
    );
  return (
    <span>
      {typeof value === "boolean" ? (value ? "Yes" : "No") : String(value)}
    </span>
  );
}
