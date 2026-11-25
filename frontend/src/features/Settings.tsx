import { displayTimezone } from "../lib/site";
import SyncControl from "../components/SyncControl";
import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router";
import { usePage } from "../app/Shell";
import { useApi } from "../api/hooks";
import { api, clearProtected, localDesktop } from "../api/transport";
import {
  ActionFeedback,
  Badge,
  Card,
  DirtyGuard,
  Empty,
  LoadState,
  Modal,
  RevisionConflict,
  useAction,
} from "../components/ui";
import ExportPanel from "../components/ExportPanel";
import { label, list, object, text } from "../lib/display";
const sections = [
  "Profile",
  "Schedule",
  "Devices",
  "Security",
  "Data & backups",
  "Sharing",
];
export default function Settings() {
  const { readOnly } = usePage();
  const query = useApi(!readOnly ? "/api/v1/settings" : null);
  if (readOnly)
    return (
      <Card title="Owner settings unavailable">
        <p>This context has read-only access to shared records.</p>
      </Card>
    );
  return (
    <LoadState loading={query.isPending} error={query.error}>
      {query.data && (
        <SettingsForm key={text(query.data.etag)} initial={query.data} />
      )}
    </LoadState>
  );
}
function SettingsForm({ initial }: { initial: Record<string, unknown> }) {
  const data = object(initial.data),
    windows = object(data.pulmonary_windows);
  const ref = useRef<HTMLFormElement>(null),
    action = useAction(),
    navigate = useNavigate();
  const [dirty, setDirty] = useState(false),
    [active, setActive] = useState("Profile"),
    [exportOpen, setExportOpen] = useState(false),
    [deleteOpen, setDeleteOpen] = useState(false),
    [eventsOpen, setEventsOpen] = useState(false),
    [etag, setEtag] = useState(text(initial.etag)),
    [latest, setLatest] = useState<Record<string, unknown> | null>(null);
  const security = useApi("/api/v1/security/status"),
    devices = useApi("/api/v1/devices"),
    sessions = useApi("/api/v1/security/sessions"),
    grants = useApi("/api/v1/sharing/grants"),
    events = useApi(eventsOpen ? "/api/v1/security/access-events" : null);
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        const item = entries.find((e) => e.isIntersecting);
        if (item)
          setActive(item.target.getAttribute("data-section") || "Profile");
      },
      { rootMargin: "-10% 0px -65% 0px" },
    );
    document
      .querySelectorAll("[data-section]")
      .forEach((element) => observer.observe(element));
    return () => observer.disconnect();
  }, []);
  async function save() {
    if (!ref.current?.reportValidity()) return false;
    const fd = new FormData(ref.current);
    const body = {
      display_name: fd.get("display_name"),
      time_format: fd.get("time_format"),
      timezone: fd.get("timezone"),
      weight_unit: fd.get("weight_unit"),
      morning_sync: false,
      pulmonary_windows: Object.fromEntries(
        ["morning", "noon", "evening"].map((slot) => [
          slot,
          [fd.get(slot + "-start"), fd.get(slot + "-end")],
        ]),
      ),
    };
    try {
      await action.run("/api/v1/settings", body, { method: "PATCH", etag });
      setDirty(false);
      return true;
    } catch {
      try {
        setLatest(object(await api("/api/v1/settings")));
      } catch {
        /* transport handles lost scope */
      }
      return false;
    }
  }
  return (
    <div className="stack">
      <div className="row between">
        <p className="muted">
          Preferences change future organization, not historical record dates.
        </p>
        <button
          className="primary"
          disabled={!dirty || action.busy}
          onClick={() => void save()}
        >
          {action.busy ? "Saving…" : "Save changes"}
        </button>
      </div>
      <nav className="row" aria-label="Settings sections">
        {sections.map((name) => (
          <a
            key={name}
            href={"#settings-" + name.toLowerCase().replaceAll(" ", "-")}
            className={active === name ? "danger" : ""}
            aria-current={active === name ? "location" : undefined}
          >
            {name}
          </a>
        ))}
      </nav>
      <form
        className="grid2"
        ref={ref}
        onChange={() => setDirty(true)}
        onSubmit={(e) => {
          e.preventDefault();
          void save();
        }}
      >
        <div className="stack">
          <div id="settings-profile" data-section="Profile">
            <Card title="Profile">
              <div className="form">
                <label className="field">
                  Display name
                  <input
                    name="display_name"
                    defaultValue={text(data.display_name, "")}
                    maxLength={80}
                  />
                </label>
                <div className="grid2">
                  <label className="field">
                    Weight display
                    <select
                      name="weight_unit"
                      defaultValue={text(data.weight_unit, "lb")}
                    >
                      <option>lb</option>
                      <option>kg</option>
                    </select>
                  </label>
                  <label className="field">
                    Time display
                    <select
                      name="time_format"
                      defaultValue={text(data.time_format, "12h")}
                    >
                      <option>12h</option>
                      <option>24h</option>
                    </select>
                  </label>
                </div>
              </div>
            </Card>
          </div>
          <div id="settings-schedule" data-section="Schedule">
            <Card title="Collection schedule">
              <div className="form">
                <label className="field">
                  Timezone
                  <input
                    name="timezone"
                    defaultValue={text(data.timezone, displayTimezone)}
                    required
                  />
                </label>
                <div className="keyValue">
                  <strong>Morning weight</strong>
                  <span>After waking</span>
                </div>
                {["morning", "noon", "evening"].map((slot) => (
                  <div className="grid2" key={slot}>
                    <label className="field">
                      {label(slot)} starts
                      <input
                        name={slot + "-start"}
                        defaultValue={text(list(windows[slot])[0], "")}
                        pattern="[0-9]{2}:[0-9]{2}"
                        required
                      />
                    </label>
                    <label className="field">
                      Ends (exclusive)
                      <input
                        name={slot + "-end"}
                        defaultValue={text(list(windows[slot])[1], "")}
                        pattern="[0-9]{2}:[0-9]{2}"
                        required
                      />
                    </label>
                  </div>
                ))}
                <p className="small muted">
                  Minimum one recorded session; three slots preferred. These are
                  organization preferences, not clinical instructions or enabled
                  notifications.
                </p>
                <div className="keyValue">
                  <strong>Nightly upload target</strong>
                  <span>00:00 · best effort</span>
                </div>
                <p className="small muted">
                  Morning sleep sync is unavailable until verified native
                  support exists.
                </p>
                <SyncControl />
              </div>
            </Card>
          </div>
          <div id="settings-devices" data-section="Devices">
            <Card title="Devices & sources">
              {list(devices.data?.items || devices.data?.devices)
                .map(object)
                .map((device) => (
                  <div className="keyValue" key={text(device.id)}>
                    <div>
                      <strong>{text(device.label, "Registered device")}</strong>
                      <p className="small muted">
                        {device.revoked ? "Revoked" : "Registered"}
                      </p>
                    </div>
                    <button
                      type="button"
                      className="danger"
                      onClick={() => {
                        if (
                          confirm(
                            "Revoke this device? Retained history is not deleted.",
                          )
                        )
                          void action
                            .run(
                              "/api/v1/devices/" + text(device.id) + "/revoke",
                              {},
                            )
                            .catch(() => {});
                      }}
                    >
                      Revoke device
                    </button>
                  </div>
                ))}
              {!list(devices.data?.items || devices.data?.devices).length && (
                <Empty>
                  No registered phone. Native pairing is not yet configured.
                </Empty>
              )}
              <div className="keyValue">
                <span>Body composition scale</span>
                <Badge>Planned</Badge>
              </div>
              <div className="keyValue">
                <span>Manual weight / breathing</span>
                <span>Available</span>
              </div>
            </Card>
          </div>
        </div>
        <div className="stack">
          <div id="settings-security" data-section="Security">
            <Card title="Security">
              <div className="keyValue">
                <strong>Access</strong>
                <span>
                  {localDesktop
                    ? "Local desktop · no login"
                    : "Password session"}
                </span>
              </div>
              {!localDesktop && (
                <div className="row">
                  <Link to="/reauthenticate">Verify password</Link>
                  <Link to="/change-password">Change password</Link>
                  <Link to="/reset-password">Recovery</Link>
                </div>
              )}
              <h3 style={{ marginTop: 20 }}>Encryption model</h3>
              <p>Trusted backend</p>
              <p className="small muted">
                The authorized Pi processes your records. Storage is encrypted;
                this is not end-to-end encryption.
              </p>
              <details style={{ marginTop: 20 }}>
                <summary>Active sessions</summary>
                {list(sessions.data?.items)
                  .map(object)
                  .map((session) => (
                    <div className="keyValue" key={text(session.id)}>
                      <span>
                        {session.current ? "This session" : "Other session"}
                        <br />
                        <span className="small muted">
                          Expires {text(session.expires_at)}
                        </span>
                      </span>
                      {!session.current && (
                        <button
                          type="button"
                          onClick={() =>
                            void action
                              .run(
                                "/api/v1/security/sessions/" +
                                  text(session.id) +
                                  "/revoke",
                                {},
                              )
                              .catch(() => {})
                          }
                        >
                          Revoke
                        </button>
                      )}
                    </div>
                  ))}
              </details>
            </Card>
          </div>
          <div id="settings-data-&-backups" data-section="Data & backups">
            <Card title="Data & backups">
              <div className="keyValue">
                <strong>Backups</strong>
                <span>
                  {security.data?.backup === "disabled_by_owner"
                    ? "Disabled by your choice"
                    : label(security.data?.backup || "unknown")}
                </span>
              </div>
              <div className="keyValue">
                <strong>Restore</strong>
                <span>{label(security.data?.restore || "not_verified")}</span>
              </div>
              <p className="small muted">
                Your local journal is not automatically backed up.
              </p>
              <div className="row" style={{ marginTop: 16 }}>
                <button type="button" onClick={() => setExportOpen(true)}>
                  Export my data
                </button>
                <button type="button" onClick={() => setEventsOpen(true)}>
                  View access history
                </button>
              </div>
            </Card>
          </div>
          <div id="settings-sharing" data-section="Sharing">
            <Card title="Sharing">
              <p>
                {
                  list(grants.data?.items)
                    .map(object)
                    .filter((g) => g.state === "active").length
                }{" "}
                active doctor grants
              </p>
              <p className="small muted">
                Pending invitations are not active access.
              </p>
              <Link to="/doctor-review">Manage doctor access →</Link>
            </Card>
          </div>
          <Card title="Close local journal">
            <p className="small muted">
              Accepted deletion blocks access immediately and purges live
              content within 24 hours. Device access is revoked. Previously
              downloaded copies cannot be recalled.
            </p>
            <button
              className="danger"
              type="button"
              style={{ marginTop: 16 }}
              onClick={() => setDeleteOpen(true)}
            >
              Delete account and records
            </button>
          </Card>
        </div>
      </form>
      <ActionFeedback action={action} />
      <RevisionConflict
        error={action.error}
        current={
          <p>
            Saved timezone: {text(object(latest?.data).timezone)}; weight:{" "}
            {text(object(latest?.data).weight_unit)}
          </p>
        }
        local={<p>Your staged changes remain in the form.</p>}
        onReload={() => {
          setEtag(text(latest?.etag));
          action.setError(null);
        }}
      />
      <DirtyGuard dirty={dirty} onSave={save} />
      {exportOpen && (
        <Modal title="Export my data" onClose={() => setExportOpen(false)}>
          <p>
            Includes retained historical revisions, private journal records and
            original documents. Each part is separately downloaded.
          </p>
          <ExportPanel body={{ format: "owner_archive" }} />
        </Modal>
      )}
      {eventsOpen && (
        <Modal title="Access history" onClose={() => setEventsOpen(false)}>
          <div className="tableWrap">
            <table>
              <thead>
                <tr>
                  <th>Action</th>
                  <th>Outcome</th>
                  <th>Time</th>
                </tr>
              </thead>
              <tbody>
                {list(events.data?.items)
                  .map(object)
                  .map((e) => (
                    <tr key={text(e.id)}>
                      <td>{label(e.action)}</td>
                      <td>{label(e.outcome)}</td>
                      <td>{text(e.created_at)}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </Modal>
      )}
      {deleteOpen && (
        <Modal
          title="Permanently close this journal?"
          onClose={() => setDeleteOpen(false)}
        >
          <form
            className="form"
            onSubmit={(e) => {
              e.preventDefault();
              void action
                .run("/api/v1/account/deletion-requests", {
                  scope: "account",
                  confirm: true,
                })
                .then(() => {
                  setDirty(false);
                  clearProtected();
                  void navigate("/account-deleted");
                })
                .catch(() => {});
            }}
          >
            <p>
              Records become inaccessible immediately. Local purge completes
              within 24 hours. Backups are disabled.
            </p>
            <label className="check">
              <input type="checkbox" required />I understand and want to delete
              this account and its records.
            </label>
            <button className="primary" disabled={action.busy}>
              Delete account and records
            </button>
            <ActionFeedback action={action} />
          </form>
        </Modal>
      )}
    </div>
  );
}
