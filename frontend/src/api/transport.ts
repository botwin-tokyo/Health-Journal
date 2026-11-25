import createClient from "openapi-fetch";
import type { paths } from "./generated";
import { QueryClient } from "@tanstack/react-query";
import { z } from "zod";

const origin = __SAMPLE_MODE__
  ? "https://sample.example.invalid"
  : new URL(import.meta.env.VITE_API_BASE_URL || "https://localhost:8443/api/v1").origin;
if (!origin.startsWith("https://"))
  throw Error("An HTTPS API origin is required");
export const sessionSchema = z
  .object({
    account_id: z.string(),
    role: z.enum(["owner", "doctor"]),
    context: z.object({
      owner_id: z.string().nullable(),
      grant_id: z.string().nullable(),
      view_mode: z.string(),
    }),
    permission_epoch: z.string(),
    csrf_token: z.string(),
    idle_expires_at: z.string(),
    absolute_expires_at: z.string(),
    server_time: z.string().optional(),
    capabilities: z.array(z.string()),
    sample_data: z.boolean().optional(),
    auth_actions: z
      .array(
        z.object({
          rel: z.string(),
          label: z.string(),
          href: z.string(),
          method: z.string(),
        }),
      )
      .optional(),
  })
  .passthrough();
export type Session = z.infer<typeof sessionSchema>;
export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    public requestId = "",
    public details: unknown = null,
    public retryAfter = 0,
  ) {
    super(code.replaceAll("_", " "));
  }
}
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30000,
      gcTime: 0,
      refetchOnWindowFocus: false,
      retry: (count, error) =>
        count < 2 &&
        (!(error instanceof ApiError) ||
          [502, 503, 504].includes(error.status)),
      retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 4000),
    },
    mutations: { retry: false },
  },
});
let state: {
  session: Session | null;
  generation: number;
  phase: "checking" | "ready" | "signed_out" | "locked" | "closed";
  preview: string | null;
} = { session: null, generation: 0, phase: "checking", preview: null };
let bootstrapSuspended = false;
let csrf = "",
  deadline = 0,
  serverDelta = 0;
const listeners = new Set<() => void>(),
  cleaners = new Set<() => void>(),
  controllers = new Set<AbortController>();
const channel =
  typeof BroadcastChannel !== "undefined"
    ? new BroadcastChannel("health03-context")
    : null;
const emit = () => listeners.forEach((fn) => fn());
export const authStore = {
  subscribe(fn: () => void) {
    listeners.add(fn);
    return () => {
      listeners.delete(fn);
    };
  },
  snapshot: () => state,
};
export function registerCleanup(fn: () => void) {
  cleaners.add(fn);
  return () => {
    cleaners.delete(fn);
  };
}
export function clearProtected(
  phase: typeof state.phase = "signed_out",
  broadcast = false,
) {
  controllers.forEach((c) => c.abort());
  controllers.clear();
  cleaners.forEach((fn) => fn());
  queryClient.clear();
  state = {
    ...state,
    session: null,
    generation: state.generation + 1,
    phase: bootstrapSuspended ? "closed" : phase,
  };
  deadline = 0;
  emit();
  if (broadcast) channel?.postMessage("reset");
}
export function remainingSeconds() {
  return Math.max(0, (deadline - performance.now()) / 1000);
}
function establish(value: unknown, response?: Response) {
  const session = sessionSchema.parse(value);
  if (
    state.session &&
    state.session.permission_epoch !== session.permission_epoch
  )
    clearProtected("checking");
  const server = Date.parse(
    session.server_time ||
      response?.headers.get("Date") ||
      new Date().toISOString(),
  );
  serverDelta = server - performance.now();
  deadline =
    Math.min(
      Date.parse(session.idle_expires_at),
      Date.parse(session.absolute_expires_at),
    ) - serverDelta;
  csrf = session.csrf_token;
  state = { ...state, session, phase: "ready" };
  emit();
  return session;
}
function isPublic(path: string) {
  return (
    path === "/internal/local-session" ||
    path === "/api/v1/auth/bootstrap" ||
    path === "/api/v1/auth/invitation" ||
    path.startsWith("/_allauth/")
  );
}
async function secureFetch(input: Request) {
  const url = new URL(input.url);
  if (url.origin !== origin) throw new ApiError(400, "invalid_api_origin");
  const isSession = url.pathname === "/api/v1/session";
  if (!isPublic(url.pathname) && !isSession && !state.session)
    throw new ApiError(401, "authentication_required");
  if (
    state.preview &&
    !["GET", "HEAD"].includes(input.method) &&
    !isPublic(url.pathname) &&
    url.pathname !== "/api/v1/session/activity"
  )
    throw new ApiError(403, "read_only_preview");
  const generation = state.generation;
  const controller = new AbortController();
  controllers.add(controller);
  input.signal.addEventListener("abort", () => controller.abort(), {
    once: true,
  });
  const headers = new Headers(input.headers);
  if (!["GET", "HEAD"].includes(input.method)) headers.set("X-CSRFToken", csrf);
  if (
    state.preview &&
    (input.method === "GET" || url.pathname === "/api/v1/journal/search")
  )
    url.searchParams.set("view_grant_id", state.preview);
  try {
    const response = await fetch(url, {
      method: input.method,
      headers,
      credentials: "include",
      cache: "no-store",
      redirect: "error",
      referrerPolicy: "no-referrer",
      signal: controller.signal,
      body: ["GET", "HEAD"].includes(input.method)
        ? undefined
        : await input.arrayBuffer(),
    });
    if (generation !== state.generation)
      throw new ApiError(409, "permission_context_changed");
    if (response.status === 401 || response.status === 403) {
      if (!isPublic(url.pathname)) {
        clearProtected();
      }
      throw new ApiError(
        response.status,
        response.status === 401
          ? "authentication_required"
          : "access_unavailable",
      );
    }
    if (!response.ok) {
      let error: unknown;
      try {
        error = await response.clone().json();
      } catch {
        error = null;
      }
      const parsed = z
        .object({
          error: z
            .object({ code: z.string(), field_errors: z.unknown().optional() })
            .optional(),
          code: z.string().optional(),
        })
        .safeParse(error);
      throw new ApiError(
        response.status,
        parsed.success
          ? parsed.data.error?.code || parsed.data.code || "request_failed"
          : "request_failed",
        response.headers.get("X-Request-ID") || "",
        error,
        Number(response.headers.get("Retry-After") || 0),
      );
    }
    if (
      url.pathname === "/api/v1/account/deletion-requests" &&
      input.method === "POST"
    ) {
      z.object({
        accepted_at: z.string(),
        purge_by: z.string(),
        durability: z.string(),
      }).parse(await response.clone().json());
      bootstrapSuspended = true;
      clearProtected("signed_out", true);
      return response;
    }
    const epoch = response.headers.get("X-Permission-Epoch");
    if (
      !isPublic(url.pathname) &&
      !isSession &&
      state.session &&
      epoch !== state.session.permission_epoch
    ) {
      const ack = response.headers.get("Content-Type")?.includes("json")
        ? ((await response.clone().json()) as Record<string, unknown>)
        : {};
      clearProtected("checking");
      await refreshSession();
      if (ack.context_reset_required !== true)
        throw new ApiError(409, "permission_context_changed");
    }
    return response;
  } finally {
    controllers.delete(controller);
  }
}
export const client = createClient<paths>({
  baseUrl: origin,
  fetch: secureFetch,
});
export async function api(
  path: string,
  options: {
    method?: string;
    body?: unknown;
    etag?: string;
    key?: string;
    signal?: AbortSignal;
    headers?: Record<string, string>;
    binary?: boolean;
  } = {},
) {
  if (!path.startsWith("/") || path.startsWith("//"))
    throw new ApiError(400, "invalid_route");
  const method = options.method || "GET";
  const headers: Record<string, string> = { ...options.headers };
  if (options.etag) headers["If-Match"] = options.etag;
  if (options.key) headers["Idempotency-Key"] = options.key;
  // The generated client is the single JSON protocol adapter. Blob uploads/downloads share its protected fetch boundary.
  if (options.body instanceof Blob || options.binary) {
    const response = await secureFetch(
      new Request(origin + path, {
        method,
        headers: {
          ...headers,
          ...(options.body instanceof Blob
            ? {
                "Content-Type": options.body.type || "application/octet-stream",
              }
            : {}),
        },
        body: options.body instanceof Blob ? options.body : undefined,
        signal: options.signal,
      }),
    );
    return options.binary ? response.arrayBuffer() : response.json();
  }
  const result = await client.request(
    method.toLowerCase() as "get",
    path as "/api/v1/session",
    { body: options.body as never, headers, signal: options.signal },
  );
  return result.data as unknown;
}
export async function bootstrap() {
  const value = await api("/api/v1/auth/bootstrap");
  csrf = z.object({ csrf_token: z.string() }).parse(value).csrf_token;
}
export const localDesktop =
  import.meta.env.VITE_LOCAL_DESKTOP === "1" &&
  location.hostname === "localhost";
export async function enterLocal() {
  await bootstrap();
  await api("/internal/local-session", { method: "POST", body: {} });
}
export async function refreshSession() {
  if (bootstrapSuspended) return null;
  if (localDesktop && !state.session) await enterLocal();
  const generation = state.generation;
  try {
    const value = await api("/api/v1/session");
    if (generation !== state.generation) return null;
    return establish(value);
  } catch (error) {
    if (generation === state.generation) clearProtected();
    throw error;
  }
}
export async function login(email: string, password: string) {
  await bootstrap();
  await api("/_allauth/browser/v1/auth/login", {
    method: "POST",
    body: { email, password },
  });
  await bootstrap();
  return refreshSession();
}
export async function logout() {
  try {
    await api("/_allauth/browser/v1/auth/session", { method: "DELETE" });
  } finally {
    state = { ...state, preview: null };
    clearProtected("signed_out", true);
  }
}
export async function authAction(path: string, body: unknown) {
  await bootstrap();
  return api("/_allauth/browser/v1/" + path, { method: "POST", body });
}
export async function preview(grant: string | null) {
  clearProtected("checking", true);
  state = { ...state, preview: grant };
  return refreshSession();
}
export async function switchContext(grant_id: string) {
  await api("/api/v1/session/context", {
    method: "POST",
    body: { grant_id },
    key: crypto.randomUUID(),
  });
  await refreshSession();
}
export function safeAction(href: string) {
  const url = new URL(href, location.origin);
  if (![origin, location.origin].includes(url.origin))
    throw Error("Untrusted authentication action");
  return url;
}
let started = false;
export function startSessionLifecycle() {
  if (started) return;
  started = true;
  void refreshSession().catch(() => {});
  let lastActivity = 0;
  const activity = (event: Event) => {
    if (
      !event.isTrusted ||
      document.hidden ||
      !state.session ||
      performance.now() - lastActivity < 60000
    )
      return;
    lastActivity = performance.now();
    void api("/api/v1/session/activity", { method: "POST", body: {} })
      .then((value) => {
        const v = z.object({ idle_expires_at: z.string() }).parse(value);
        if (state.session) {
          deadline =
            Math.min(
              Date.parse(v.idle_expires_at),
              Date.parse(state.session.absolute_expires_at),
            ) - serverDelta;
        }
      })
      .catch(() => {});
  };
  ["pointerdown", "keydown", "touchstart"].forEach((name) =>
    window.addEventListener(name, activity, { passive: true }),
  );
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) clearProtected("locked");
    else {
      clearProtected("checking");
      void refreshSession().catch(() => {});
    }
  });
  window.addEventListener("pageshow", (event) => {
    if (event.persisted) {
      clearProtected("checking");
      void refreshSession().catch(() => {});
    }
  });
  channel?.addEventListener("message", () => {
    clearProtected("checking");
    void refreshSession().catch(() => {});
  });
  setInterval(() => {
    if (state.session && remainingSeconds() === 0) {
      clearProtected(localDesktop ? "checking" : "signed_out");
      if (localDesktop) void refreshSession().catch(() => {});
    }
  }, 1000);
  setInterval(() => {
    if (state.session && !document.hidden)
      void refreshSession().catch(() => {});
  }, 30000);
}
