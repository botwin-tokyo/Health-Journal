import { useState } from "react";
import { usePage } from "../app/Shell";
import { useApi, records } from "../api/hooks";
import { api } from "../api/transport";
import { dateLabel, label, object, shiftDate, text } from "../lib/display";
import { ActionFeedback, Badge, Card, Empty, useAction } from "./ui";
export default function BaselineEditor({
  metric,
  slot,
}: {
  metric: string;
  slot?: string;
}) {
  const { date, readOnly } = usePage(),
    action = useAction();
  const query = useApi("/api/v1/baselines?weight_unit=lb");
  const [result, setResult] = useState<Record<string, unknown> | null>(null),
    [selection, setSelection] = useState<Record<string, unknown> | null>(null);
  return (
    <div className="stack">
      <p>
        Recent references use the previous 28 days and need 14 eligible days. A
        fixed reference is an immutable selection you explicitly review and
        save.
      </p>
      {records(query.data?.items)
        .filter(
          (r) => r.data.metric_id === metric && (!slot || r.data.slot === slot),
        )
        .map((r) => (
          <Card key={r.id} title="Fixed personal reference">
            <p>
              {text(r.data.display_value || r.data.value)}{" "}
              {text(r.data.display_unit || r.data.unit, "")}
            </p>
            <p className="small muted">
              {dateLabel(text(r.data.from_date, ""))} –{" "}
              {dateLabel(text(r.data.to_date, ""))} ·{" "}
              {label(r.data.method_version)}
            </p>
            <Badge>{text(r.data.contributor_day_count)} eligible days</Badge>
            {!readOnly && (
              <button
                className="danger"
                onClick={() =>
                  void action
                    .run(
                      "/api/v1/baselines/" + r.id + "/retire",
                      {},
                      { etag: r.etag },
                    )
                    .catch(() => {})
                }
              >
                Retire reference
              </button>
            )}
          </Card>
        ))}
      {!readOnly && (
        <form
          className="form"
          onChange={() => {
            setResult(null);
            setSelection(null);
          }}
          onSubmit={(event) => {
            event.preventDefault();
            const fd = new FormData(event.currentTarget);
            const body = {
              metric_id: metric,
              from: fd.get("from"),
              to: fd.get("to"),
              weight_unit: "lb",
              ...(slot ? { slot } : {}),
            };
            setSelection(body);
            void api("/api/v1/baselines/preview", { method: "POST", body })
              .then((value) => setResult(object(value)))
              .catch(action.setError);
          }}
        >
          <div className="grid2">
            <label className="field">
              From
              <input
                name="from"
                type="date"
                defaultValue={shiftDate(date, -28)}
                required
              />
            </label>
            <label className="field">
              To
              <input
                name="to"
                type="date"
                defaultValue={shiftDate(date, -1)}
                required
              />
            </label>
          </div>
          <button>Review fixed reference</button>
        </form>
      )}
      {result && (
        <Card title="Reference preview">
          <p>
            {text(result.display_value || result.value)}{" "}
            {text(result.display_unit || result.unit, "")}
          </p>
          <p>
            {text(result.contributor_day_count)} eligible days ·{" "}
            {label(result.method_version)}
          </p>
          <p className="small">
            Middle 50% of observed readings:{" "}
            {text(result.display_p25 ?? result.p25)}–
            {text(result.display_p75 ?? result.p75)}. This is observed
            variation, not a clinical threshold.
          </p>
          {result.eligible === true ? (
            <button
              className="primary"
              disabled={action.busy}
              onClick={() =>
                void action
                  .run("/api/v1/baselines", {
                    ...selection,
                    source_epoch: result.source_epoch,
                    preview_fingerprint: result.preview_fingerprint,
                  })
                  .then(() => setResult(null))
                  .catch(() => {})
              }
            >
              Save immutable reference
            </button>
          ) : (
            <Empty>
              Building baseline: not enough compatible eligible readings.
            </Empty>
          )}
        </Card>
      )}
      <ActionFeedback action={action} />
    </div>
  );
}
