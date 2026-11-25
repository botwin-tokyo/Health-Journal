import {
  useEffect,
  useId,
  useRef,
  useState,
  useSyncExternalStore,
  type ReactNode,
} from "react";
import { useBlocker } from "react-router";
import { ApiError, api, queryClient } from "../api/transport";
import { label, text } from "../lib/display";
import type { ClinicalRecord } from "../api/hooks";
export function Card({
  title,
  children,
  className = "",
  id,
}: {
  title?: string;
  children: ReactNode;
  className?: string;
  id?: string;
}) {
  return (
    <section id={id} className={"card " + className}>
      {title && <h2 className="cardTitle">{title}</h2>}
      {children}
    </section>
  );
}
export function Badge({
  children,
  tone = "",
}: {
  children: ReactNode;
  tone?: string;
}) {
  return <span className={"badge " + tone}>{children}</span>;
}
export function Metric({
  title,
  value,
  unit = "",
  note,
  hero = false,
}: {
  title: string;
  value: unknown;
  unit?: string;
  note?: ReactNode;
  hero?: boolean;
}) {
  return (
    <Card className={"metric " + (hero ? "hero" : "")}>
      <div className="row between">
        <strong>{title}</strong>
        <span className="mono" aria-hidden="true">
          ╱
        </span>
      </div>
      <div className="value">
        {text(value)}
        {value != null && <small>{unit}</small>}
      </div>
      <div className="muted small">{note || "Awaiting data"}</div>
    </Card>
  );
}
export function Empty({
  children = "No records for this selection.",
}: {
  children?: ReactNode;
}) {
  return <div className="empty">{children}</div>;
}
export function ErrorBox({ error }: { error: unknown }) {
  if (!error) return null;
  const e = error instanceof ApiError ? error : null;
  return (
    <div role="alert" className="error" tabIndex={-1}>
      <strong>
        {e?.status === 412
          ? "This record changed. Review the saved version before retrying."
          : e?.status === 429
            ? "Please wait before trying again."
            : e?.status === 503
              ? "The Pi cannot process this request right now."
              : e?.message ||
                "Unable to complete this request. Please try again."}
      </strong>
      {e?.requestId && (
        <p className="small">Support reference: {e.requestId}</p>
      )}
    </div>
  );
}
export function LoadState({
  loading,
  error,
  children,
}: {
  loading: boolean;
  error: unknown;
  children: ReactNode;
}) {
  if (error) return <ErrorBox error={error} />;
  if (loading)
    return (
      <div className="skeleton" role="status" aria-label="Loading records" />
    );
  return <>{children}</>;
}
export function Segments({
  values,
  value,
  onChange,
  label: ariaLabel,
}: {
  values: string[];
  value: string;
  onChange: (v: string) => void;
  label: string;
}) {
  return (
    <div className="segmented" role="group" aria-label={ariaLabel}>
      {values.map((v) => (
        <button
          key={v}
          type="button"
          aria-pressed={v === value}
          onClick={() => onChange(v)}
        >
          {label(v)}
        </button>
      ))}
    </div>
  );
}
export function Modal({
  title,
  children,
  onClose,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null),
    id = useId();
  const changed = useRef(false);
  const close = () => {
    if (
      !changed.current ||
      window.confirm("Discard the unsaved changes in this dialog?")
    )
      onClose();
  };
  useEffect(() => {
    const element = ref.current;
    const trigger = document.activeElement as HTMLElement | null;
    element?.showModal();
    return () => {
      element?.close();
      trigger?.focus();
    };
  }, []);
  return (
    <dialog
      ref={ref}
      aria-labelledby={id}
      onChange={() => {
        changed.current = true;
      }}
      onCancel={(event) => {
        event.preventDefault();
        close();
      }}
    >
      <div className="row between">
        <h2 id={id}>{title}</h2>
        <button
          type="button"
          className="quiet"
          aria-label="Close dialog"
          onClick={close}
        >
          ×
        </button>
      </div>
      {children}
    </dialog>
  );
}
const dirtyEntries = new Map<string, () => Promise<boolean>>();
export function confirmPendingChange() {
  return (
    dirtyEntries.size === 0 ||
    window.confirm("Discard unsaved changes before changing this selection?")
  );
}
const dirtyListeners = new Set<() => void>();
const notifyDirty = () => dirtyListeners.forEach((fn) => fn());
export function DirtyGuard({
  dirty,
  onSave,
}: {
  dirty: boolean;
  onSave?: () => Promise<boolean>;
}) {
  const id = useId(),
    save = useRef(onSave);
  useEffect(() => {
    save.current = onSave;
  }, [onSave]);
  useEffect(() => {
    if (!dirty) return;
    dirtyEntries.set(id, () => save.current?.() || Promise.resolve(false));
    notifyDirty();
    return () => {
      dirtyEntries.delete(id);
      notifyDirty();
    };
  }, [dirty, id]);
  return null;
}
export function PendingChanges() {
  const count = useSyncExternalStore(
    (fn) => {
      dirtyListeners.add(fn);
      return () => {
        dirtyListeners.delete(fn);
      };
    },
    () => dirtyEntries.size,
  );
  const blocker = useBlocker(count > 0);
  const onSave = async () => {
    for (const save of [...dirtyEntries.values()])
      if (!(await save())) return false;
    return true;
  };
  useEffect(() => {
    if (!count) return;
    const fn = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", fn);
    return () => window.removeEventListener("beforeunload", fn);
  }, [count]);
  return blocker.state === "blocked" ? (
    <Modal title="Unsaved changes" onClose={() => blocker.reset()}>
      <p>
        Your changes are only in this tab. Save them or discard them before
        leaving.
      </p>
      <div className="dialogActions">
        <button onClick={() => blocker.reset()}>Keep editing</button>
        <button onClick={() => blocker.proceed()}>Discard</button>
        {onSave && (
          <button
            className="primary"
            onClick={() =>
              void onSave().then((ok) => {
                if (ok) blocker.proceed();
              })
            }
          >
            Save and leave
          </button>
        )}
      </div>
    </Modal>
  ) : null;
}
export function Provenance({ record }: { record: ClinicalRecord }) {
  return (
    <details>
      <summary>Source & record details</summary>
      <dl className="small">
        <dt>Recorded date</dt>
        <dd>{record.clinical_date || "Not supplied"}</dd>
        <dt>Source</dt>
        <dd>{label(record.data.source_type)}</dd>
        <dt>Precision</dt>
        <dd>{label(record.data.time_precision)}</dd>
        <dt>Qualification</dt>
        <dd>{label(record.data.qualification)}</dd>
        <dt>Revision</dt>
        <dd className="mono">{record.revision_id}</dd>
        <dt>Original value</dt>
        <dd>
          {text(record.data.value)} {text(record.data.unit, "")}
        </dd>
      </dl>
    </details>
  );
}
const uploadIds = new WeakMap<Blob, string>();
export function useAction() {
  const [error, setError] = useState<unknown>(null),
    [busy, setBusy] = useState(false),
    [message, setMessage] = useState("");
  const last = useRef<{ signature: string; key: string } | null>(null);
  async function run(
    path: string,
    body: unknown,
    options: {
      method?: string;
      etag?: string;
      headers?: Record<string, string>;
    } = {},
  ) {
    if (body instanceof Blob && !uploadIds.has(body))
      uploadIds.set(body, crypto.randomUUID());
    const signature =
      path +
      JSON.stringify(
        body instanceof Blob
          ? { id: uploadIds.get(body), size: body.size, type: body.type }
          : body,
      ) +
      JSON.stringify(options);
    if (last.current?.signature !== signature)
      last.current = { signature, key: crypto.randomUUID() };
    setBusy(true);
    setError(null);
    setMessage("");
    try {
      const result = await api(path, {
        ...options,
        method: options.method || "POST",
        body,
        key: last.current.key,
      });
      last.current = null;
      await queryClient.invalidateQueries();
      setMessage("Saved");
      return result;
    } catch (e) {
      setError(e);
      throw e;
    } finally {
      setBusy(false);
    }
  }
  return { error, busy, message, run, setError, setMessage };
}
export function ActionFeedback({
  action,
}: {
  action: ReturnType<typeof useAction>;
}) {
  return (
    <>
      <ErrorBox error={action.error} />
      {action.message && (
        <p role="status" className="small muted">
          {action.message}
        </p>
      )}
    </>
  );
}
export function RevisionConflict({
  error,
  current,
  local,
  onReload,
}: {
  error: unknown;
  current: ReactNode;
  local: ReactNode;
  onReload: () => void;
}) {
  return error instanceof ApiError && error.status === 412 ? (
    <Card title="Compare changes">
      <div className="grid2">
        <div>
          <h3>Current saved record</h3>
          {current}
        </div>
        <div>
          <h3>Your unsaved changes</h3>
          {local}
        </div>
      </div>
      <button type="button" onClick={onReload}>
        Use current revision for my reviewed changes
      </button>
    </Card>
  ) : null;
}
