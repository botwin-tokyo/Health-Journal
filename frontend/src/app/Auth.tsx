import { lazy, Suspense, useEffect, useState } from "react";
import { Link, Navigate, Outlet, useLocation, useNavigate } from "react-router";
import { useSession } from "../api/hooks";
import {
  api,
  authAction,
  bootstrap,
  clearProtected,
  localDesktop,
  login,
  refreshSession,
  startSessionLifecycle,
} from "../api/transport";
import { Card, ErrorBox } from "../components/ui";
const GrantChooser = lazy(() =>
  import("../features/Review").then((m) => ({ default: m.GrantChooser })),
);
import { Brand } from "./Shell";
export function Boundary() {
  const { session, phase } = useSession();
  const [error, setError] = useState<unknown>(null);
  useEffect(() => startSessionLifecycle(), []);
  if (phase === "closed") return <Navigate to="/account-deleted" replace />;
  if (session && phase === "ready")
    return session.role === "doctor" && !session.context.grant_id ? (
      <main className="auth">
        <Suspense fallback={<p>Loading shared journals…</p>}>
          <GrantChooser />
        </Suspense>
      </main>
    ) : (
      <Outlet />
    );
  if (localDesktop)
    return (
      <main className="auth">
        <Card>
          <Brand />
          <h1>Your journal, on this Pi.</h1>
          <p>
            {phase === "locked"
              ? "Your records are hidden while this tab is inactive."
              : "Connecting to the local backend…"}
          </p>
          <ErrorBox error={error} />
          <button onClick={() => void refreshSession().catch(setError)}>
            Open journal
          </button>
        </Card>
      </main>
    );
  if (phase === "checking")
    return (
      <main className="auth">
        <p role="status">Checking your session…</p>
      </main>
    );
  return <Navigate to="/login" replace />;
}
export default function Auth() {
  const location = useLocation(),
    navigate = useNavigate();
  const { session, phase } = useSession();
  const mode = location.pathname.split("/")[1] || "login";
  const [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>(null),
    [message, setMessage] = useState("");
  if (phase === "closed") return <Navigate to="/account-deleted" replace />;
  if (localDesktop) return <Navigate to="/overview" replace />;
  if (session && mode === "login") return <Navigate to="/overview" replace />;
  const title =
    mode === "login"
      ? "Your health. Your journal."
      : mode === "enroll"
        ? "Accept your invitation"
        : mode === "reset-password"
          ? "Reset your password"
          : mode === "verify-email"
            ? "Verify your email"
            : mode === "change-password"
              ? "Change your password"
              : "Verify your password";
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget,
      data = new FormData(form);
    const email = String(data.get("email") || ""),
      password = String(data.get("password") || ""),
      key = String(data.get("key") || "");
    setBusy(true);
    setError(null);
    const passwordInput = form.elements.namedItem(
      "password",
    ) as HTMLInputElement | null;
    if (passwordInput) passwordInput.value = "";
    try {
      if (mode === "login") {
        await login(email, password);
        navigate("/overview");
      } else if (mode === "enroll") {
        await bootstrap();
        await api("/api/v1/auth/invitation", {
          method: "POST",
          body: { token: key },
        });
        await authAction("auth/signup", { email, password });
        setMessage(
          "Enrollment submitted. Complete email verification, then sign in.",
        );
      } else if (mode === "reset-password") {
        if (key) {
          await authAction("auth/password/reset", { key, password });
          clearProtected();
          setMessage("Password reset. Sign in with your new password.");
        } else {
          await authAction("auth/password/request", { email });
          setMessage(
            "If this account can recover, its reset instructions will be sent.",
          );
        }
      } else if (mode === "verify-email") {
        await authAction("auth/email/verify", { key });
        setMessage("Email verified. You can sign in.");
      } else if (mode === "change-password") {
        await authAction("account/password/change", {
          current_password: data.get("current_password"),
          new_password: password,
        });
        clearProtected();
        setMessage("Password changed. Sign in again.");
      } else {
        await authAction("auth/reauthenticate", { password });
        await refreshSession();
        navigate("/settings");
      }
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="auth">
      <Card>
        <Brand />
        <h1>{title}</h1>
        <p className="muted">
          Your records stay on your Pi. This dashboard only displays what you
          can access.
        </p>
        <form className="form" onSubmit={(event) => void submit(event)}>
          {["login", "enroll", "reset-password"].includes(mode) && (
            <label className="field">
              Email
              <input
                name="email"
                type="email"
                autoComplete="username"
                required={mode !== "reset-password"}
              />
            </label>
          )}
          {["enroll", "reset-password", "verify-email"].includes(mode) && (
            <label className="field">
              {mode === "enroll"
                ? "Invitation code"
                : "Verification or reset code"}
              <input
                name="key"
                autoComplete="off"
                required={mode !== "reset-password"}
              />
            </label>
          )}
          {mode === "change-password" && (
            <label className="field">
              Current password
              <input
                name="current_password"
                type="password"
                autoComplete="current-password"
                required
              />
            </label>
          )}
          {mode !== "verify-email" && (
            <label className="field">
              {mode === "reset-password"
                ? "New password (with reset code)"
                : "Password"}
              <input
                name="password"
                type="password"
                autoComplete={
                  ["enroll", "change-password", "reset-password"].includes(mode)
                    ? "new-password"
                    : "current-password"
                }
                required={mode !== "reset-password"}
              />
            </label>
          )}
          <ErrorBox error={error} />
          {message && <p role="status">{message}</p>}
          <button className="primary full" disabled={busy}>
            {busy ? "Please wait…" : mode === "login" ? "Sign in" : "Continue"}
          </button>
        </form>
        <div className="row" style={{ marginTop: 20 }}>
          <Link to="/login">Sign in</Link>
          <Link to="/reset-password">Forgot password?</Link>
        </div>
      </Card>
    </main>
  );
}
