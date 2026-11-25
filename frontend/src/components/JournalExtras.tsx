import { useState } from "react";
import { records, useApi, type ClinicalRecord } from "../api/hooks";
import { Card, Modal, ActionFeedback, useAction, Empty } from "./ui";
import { text } from "../lib/display";
export default function JournalExtras({ date }: { date: string }) {
  const query = useApi(
    "/api/v1/journal/medication-events?from=" + date + "&to=" + date,
  );
  const [editing, setEditing] = useState<ClinicalRecord | null | undefined>(
    undefined,
  );
  return (
    <Card title="Medication events">
      {records(query.data?.items).map((r) => (
        <button className="listButton" key={r.id} onClick={() => setEditing(r)}>
          {text(r.data.name)} · {text(r.data.dose, "")} {text(r.data.unit, "")}
        </button>
      ))}
      {!records(query.data?.items).length && (
        <Empty>No medication events on this date.</Empty>
      )}
      <button onClick={() => setEditing(null)}>Add medication event</button>
      {editing !== undefined && (
        <Modal
          title={editing ? "Edit medication event" : "Medication event"}
          onClose={() => setEditing(undefined)}
        >
          <SmallRecordEditor
            record={editing}
            kind="medication"
            date={date}
            onDone={() => setEditing(undefined)}
          />
        </Modal>
      )}
    </Card>
  );
}
export function SmallRecordEditor({
  record,
  kind,
  date,
  onDone,
}: {
  record: ClinicalRecord | null;
  kind: "question" | "medication";
  date: string;
  onDone: () => void;
}) {
  const action = useAction();
  const path =
    "/api/v1/journal/" +
    (kind === "question" ? "questions" : "medication-events") +
    (record ? "/" + record.id : "");
  return (
    <form
      className="form"
      onSubmit={(event) => {
        event.preventDefault();
        const fd = new FormData(event.currentTarget);
        const body = {
          clinical_date: record?.clinical_date || date,
          time_precision: record?.data.time_precision || "day",
          ...(record
            ? Object.fromEntries(
                ["measured_start", "timezone", "original_offset_minutes"]
                  .filter((k) => k in record.data)
                  .map((k) => [k, record.data[k]]),
              )
            : {}),
          visibility: record?.data.visibility || "private",
          ...(kind === "question"
            ? {
                text: fd.get("text"),
                ...(record?.data.origin_record_id
                  ? { origin_record_id: record.data.origin_record_id }
                  : {}),
              }
            : {
                name: fd.get("name"),
                dose: fd.get("dose") || null,
                unit: fd.get("unit") || "",
                note: fd.get("note") || "",
                ...(record?.data.parent_entry_id
                  ? { parent_entry_id: record.data.parent_entry_id }
                  : {}),
              }),
        };
        void action
          .run(path, body, {
            method: record ? "PATCH" : "POST",
            etag: record?.etag,
          })
          .then(onDone)
          .catch(() => {});
      }}
    >
      {kind === "question" ? (
        <label className="field">
          Question
          <textarea
            name="text"
            required
            defaultValue={text(record?.data.text, "")}
          />
        </label>
      ) : (
        <>
          <label className="field">
            Medication name
            <input
              name="name"
              required
              defaultValue={text(record?.data.name, "")}
            />
          </label>
          <label className="field">
            Dose
            <input
              name="dose"
              inputMode="decimal"
              defaultValue={text(record?.data.dose, "")}
            />
          </label>
          <label className="field">
            Unit
            <input name="unit" defaultValue={text(record?.data.unit, "")} />
          </label>
          <label className="field">
            Note
            <textarea name="note" defaultValue={text(record?.data.note, "")} />
          </label>
        </>
      )}
      <p className="small muted">
        {record
          ? "Existing sharing choice is preserved."
          : "New medication events are private."}
      </p>
      <ActionFeedback action={action} />
      <button className="primary" disabled={action.busy}>
        Save {kind}
      </button>
      {record && (
        <button
          type="button"
          className="danger"
          onClick={() => {
            if (confirm("Delete this " + kind + "?"))
              void action
                .run(path, {}, { method: "DELETE", etag: record.etag })
                .then(onDone)
                .catch(() => {});
          }}
        >
          Delete {kind}
        </button>
      )}
    </form>
  );
}
