import { useEffect, useState } from "react";
import { useApi } from "../api/hooks";
import { api, registerCleanup } from "../api/transport";
import { list, object, text, label } from "../lib/display";
import { ActionFeedback, useAction } from "./ui";
export default function ExportPanel({
  body,
  path = "/api/v1/exports",
  etag,
}: {
  body: Record<string, unknown>;
  path?: string;
  etag?: string;
}) {
  const [id, setId] = useState("");
  const action = useAction();
  const query = useApi(id ? "/api/v1/exports/" + id : null, true);
  const status = query.data || {};
  const [urls] = useState(() => new Set<string>());
  useEffect(() => {
    const clear = () => {
      urls.forEach((url) => URL.revokeObjectURL(url));
      urls.clear();
    };
    const unregister = registerCleanup(clear);
    return () => {
      unregister();
      clear();
    };
  }, [urls]);
  async function download(part: string) {
    try {
      const ticket = object(
        await action.run(`/api/v1/exports/${id}/download-tickets`, {
          part_id: part,
        }),
      );
      const bytes = (await api(
        `/api/v1/exports/${id}/content?part_id=${part}`,
        {
          binary: true,
          headers: { "X-Download-Ticket": text(ticket.ticket, "") },
        },
      )) as ArrayBuffer;
      const partInfo = list(status.parts)
        .map(object)
        .find((p) => p.id === part);
      const mime = text(
        partInfo?.mime_type,
        path.includes("/snapshots/") ? "application/pdf" : "application/json",
      );
      const extension =
        mime === "application/pdf"
          ? ".pdf"
          : mime.includes("csv")
            ? ".csv"
            : mime.includes("json")
              ? ".json"
              : ".bin";
      const url = URL.createObjectURL(new Blob([bytes], { type: mime }));
      urls.add(url);
      const a = document.createElement("a");
      a.href = url;
      a.download = "health-export-" + part + extension;
      a.click();
      setTimeout(() => {
        URL.revokeObjectURL(url);
        urls.delete(url);
      }, 1000);
    } catch (e) {
      action.setError(e);
    }
  }
  return (
    <div className="stack">
      <p>
        Creates a frozen, authorized export. Each part is bounded to 25 MiB and
        available for 24 hours.
      </p>
      {!id ? (
        <button
          className="primary"
          disabled={action.busy}
          onClick={() =>
            void action
              .run(path, body, { etag })
              .then((value) =>
                setId(text(object(value).id || object(value).job_id, "")),
              )
              .catch(() => {})
          }
        >
          Prepare export
        </button>
      ) : (
        <>
          <p role="status">{label(status.state || "queued")}</p>
          {["failed", "cancelled", "revoked"].includes(text(status.state)) && (
            <p>
              Export unavailable. Close this dialog and review the scope before
              trying again.
            </p>
          )}
          {list(status.parts).map((value) => {
            const part = object(value);
            return (
              <button
                key={text(part.id)}
                disabled={action.busy || status.state !== "ready"}
                onClick={() => void download(text(part.id))}
              >
                Download part · {text(part.bytes || part.size)} bytes
              </button>
            );
          })}
          {status.state === "ready" && !list(status.parts).length && (
            <button
              disabled={action.busy}
              onClick={() =>
                void download(
                  text(
                    status.artifact_id ||
                      status.output_record_id ||
                      status.record_id,
                    "",
                  ),
                )
              }
            >
              Download report
            </button>
          )}
        </>
      )}
      <ActionFeedback action={action} />
    </div>
  );
}
