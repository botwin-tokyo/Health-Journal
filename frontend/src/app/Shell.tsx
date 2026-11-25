import { siteName, siteTagline } from "../lib/site";
import { PendingChanges, confirmPendingChange } from "../components/ui";
import { createContext, useContext, useEffect, useRef, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router";
import {
  Home,
  HeartPulse,
  Wind,
  UserRound,
  BedDouble,
  NotebookPen,
  FlaskConical,
  Stethoscope,
  Settings,
  LogOut,
  Menu,
  X,
} from "lucide-react";
import { useApi, useSession } from "../api/hooks";
import {
  logout,
  remainingSeconds,
  preview,
  localDesktop,
} from "../api/transport";
import { dateLabel, today, text, object } from "../lib/display";
import { Badge } from "../components/ui";
import s from "./Shell.module.css";
const definitions = [
  [
    "overview",
    "Overview",
    "PERSONAL BASELINE",
    "Your measurements, in context.",
    Home,
  HeartPulse,
  ],
  [
    "breathing",
    "Breathing",
    "PULMONARY JOURNAL",
    "Sessions, individual attempts, and your personal reference.",
    Wind,
  ],
  [
    "body",
    "Body",
    "WEIGHT & COMPOSITION",
    "Morning measurements and long-term change.",
    UserRound,
  ],
  ["blood-pressure", "Blood pressure", "MONITOR READINGS", "Saved measurements and their history.", HeartPulse],
  [
    "sleep-activity",
    "Sleep & Activity",
    "REST & MOVEMENT",
    "Recorded sleep and movement, with their sources.",
    BedDouble,
  ],
  [
    "journal",
    "Journal",
    "DAILY CONTEXT",
    "What happened around the measurements.",
    NotebookPen,
  ],
  [
    "labs",
    "Labs",
    "REPORTS & RESULTS",
    "Original reports with reviewed, structured results.",
    FlaskConical,
  ],
  [
    "doctor-review",
    "Doctor Review",
    "APPOINTMENT PREPARATION",
    "A focused record for your next conversation.",
    Stethoscope,
  ],
  [
    "settings",
    "Settings",
    "PRIVACY & COLLECTION",
    "Control access, collection, and data handling.",
    Settings,
  ],
] as const;
const PageContext = createContext({
  date: today(),
  setDate: (_v: string) => {},
  range: 28,
  setRange: (_v: number) => {},
  readOnly: false,
});
export const usePage = () => useContext(PageContext);
export function Brand() {
  return (
    <div className={s.brand}>
      <span className={s.tile} aria-hidden="true" />
      <div>
        <strong>{siteName}</strong>
        <small>{siteTagline}</small>
      </div>
    </div>
  );
}
export default function Shell() {
  const { session, preview: previewId } = useSession();
  const [date, changeDate] = useState(() =>
      session?.sample_data
        ? "2026-11-07"
        : typeof session?.latest_clinical_date === "string"
          ? session.latest_clinical_date
          : today(),
    ),
    [range, setRange] = useState(28),
    [open, setOpen] = useState(false),
    [remaining, setRemaining] = useState(remainingSeconds());
  const setDate = (value: string) => {
    if (value !== date && confirmPendingChange()) changeDate(value);
  };
  const nav = useRef<HTMLElement>(null),
    menu = useRef<HTMLButtonElement>(null);
  const location = useLocation();
  const index = Math.max(
    0,
    definitions.findIndex((d) => location.pathname.startsWith("/" + d[0])),
  );
  const current = definitions[index];
  const readOnly = session?.role === "doctor" || !!previewId;
  const sync = useApi(!readOnly ? "/api/v1/sync/status" : null);
  useEffect(() => {
    document.title = current[1] + " · " + siteName;
    document.getElementById("page-title")?.focus();
  }, [current]);
  useEffect(() => {
    const timer = setInterval(() => setRemaining(remainingSeconds()), 1000);
    return () => clearInterval(timer);
  }, []);
  useEffect(() => {
    if (!open) return;
    const element = nav.current;
    const items = element?.querySelectorAll<HTMLElement>("a,button");
    items?.[0]?.focus();
    const handle = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
        menu.current?.focus();
      }
      if (event.key === "Tab" && items?.length) {
        const first = items[0],
          last = items[items.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener("keydown", handle);
    return () => document.removeEventListener("keydown", handle);
  }, [open]);
  const links = definitions.filter(
    (d) => !readOnly || !["settings"].includes(d[0]),
  );
  return (
    <PageContext value={{ date, setDate, range, setRange, readOnly }}>
      <div className={s.shell}>
        <a className="skip" href="#main">
          Skip to content
        </a>
        {open && (
          <div
            className={s.scrim}
            aria-hidden="true"
            onClick={() => setOpen(false)}
          />
        )}
        <aside
          ref={nav}
          className={s.sidebar + (open ? " " + s.open : "")}
          aria-label="Main navigation"
        >
          <Brand />
          <nav className={s.nav}>
            {links
              .filter((d) => d[0] !== "settings")
              .map(([path, title, , , Icon]) => (
                <NavLink
                  key={path}
                  to={"/" + path}
                  title={title}
                  onClick={() => setOpen(false)}
                >
                  <Icon aria-hidden="true" />
                  <span>{title}</span>
                </NavLink>
              ))}
          </nav>
          <div className={s.bottom}>
            {!readOnly && (
              <NavLink
                to="/settings"
                title="Settings"
                onClick={() => setOpen(false)}
              >
                <Settings aria-hidden="true" />
                <span>Settings</span>
              </NavLink>
            )}
            <div className={s.account}>
              <span className={s.avatar}>
                {session?.role === "doctor" ? "D" : "H"}
              </span>
              <span>{readOnly ? "Read-only view" : "Personal journal"}</span>
              {!localDesktop && (
                <button
                  className="quiet"
                  aria-label="Sign out"
                  title="Sign out"
                  onClick={() => void logout()}
                >
                  <LogOut size={18} />
                </button>
              )}
            </div>
          </div>
        </aside>
        <div className={s.main}>
          <div className={s.mobile}>
            <button
              ref={menu}
              className="quiet"
              aria-label={open ? "Close navigation" : "Open navigation"}
              aria-expanded={open}
              onClick={() => setOpen(!open)}
            >
              {open ? <X /> : <Menu />}
            </button>
            <strong>{siteName}</strong>
          </div>
          <div className={s.status} role="region" aria-label="Journal status">
            <strong>{dateLabel(date)}</strong>
            <span className="muted">
              {readOnly
                ? "Review access is not continuous monitoring"
                : text(
                    object(sync.data).last_successful_receipt,
                    "No successful phone sync",
                  )}
            </span>
            {(session?.sample_data || __SAMPLE_MODE__) && (
              <span className={s.sample}>
                <Badge>SAMPLE DATA</Badge>
              </span>
            )}
          </div>
          <main id="main" className={s.content}>
            {previewId && (
              <div className="notice row between">
                <strong>Owner preview · restricted, read-only view</strong>
                <button onClick={() => void preview(null)}>
                  Return to owner view
                </button>
              </div>
            )}
            {remaining > 0 && remaining < 120 && (
              <div role="status" className="notice">
                Your session expires soon. Save your changes; unsaved drafts are
                discarded when it expires.
              </div>
            )}
            <header className={s.heading}>
              <div>
                <div className="eyebrow">
                  {String(index + 1).padStart(2, "0")} / {current[2]}
                </div>
                <h1 id="page-title" tabIndex={-1}>
                  {current[1]}
                </h1>
                <p>{current[3]}</p>
              </div>
              <div className={s.toolbar}>
                <label className="srOnly" htmlFor="record-date">
                  Record date
                </label>
                <input
                  id="record-date"
                  className={s.date}
                  type="date"
                  value={date}
                  onChange={(e) => setDate(e.target.value)}
                />
              </div>
            </header>
            <Outlet />
            <PendingChanges />
            <footer className="pageFooter">
              <span>
                Dates follow the recorded timezone · Personal references are not
                diagnostic thresholds
              </span>
              <span>{siteName}</span>
            </footer>
          </main>
        </div>
      </div>
    </PageContext>
  );
}
