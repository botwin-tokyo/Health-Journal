import { useState } from "react";
import { useApi } from "../api/hooks";
import { list, object, text, label } from "../lib/display";
import { ActionFeedback, useAction } from "./ui";
export default function SyncControl() {
  const devices = useApi("/api/v1/devices"),
    status = useApi("/api/v1/sync/status", true),
    action = useAction();
  const available = list(devices.data?.devices)
    .map(object)
    .filter((d) => !d.revoked);
  const [choice, setChoice] = useState("");
  const device = available.find((d) => d.id === choice) || available[0];
  const last = object(list(status.data?.requests)[0]);
  return (
    <div className="stack">
      {available.length > 1 && (
        <label className="field">
          Collection phone
          <select
            value={text(device?.id, "")}
            onChange={(e) => setChoice(e.target.value)}
          >
            {available.map((d) => (
              <option key={text(d.id)} value={text(d.id)}>
                {text(d.label, "Registered phone")}
              </option>
            ))}
          </select>
        </label>
      )}
      <button
        type="button"
        disabled={!device || action.busy}
        onClick={() =>
          void action
            .run("/api/v1/sync/requests", { device_id: device.id })
            .catch(() => {})
        }
      >
        Sync now
      </button>
      <span className="small muted">
        {!device
          ? "Device unavailable · no collection phone configured"
          : last.state === "queued"
            ? "Queued — awaiting device"
            : label(last.state || "ready to request")}
      </span>
      <ActionFeedback action={action} />
    </div>
  );
}
