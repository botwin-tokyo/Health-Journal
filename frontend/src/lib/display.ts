import { displayTimezone } from "./site";
export function dateLabel(value: string | null | undefined) {
  if (!value || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return "Date unavailable";
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "2-digit",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(value + "T12:00:00Z"));
}
export function today() {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: displayTimezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
}
export function shiftDate(value: string, days: number) {
  const d = new Date(value + "T12:00:00Z");
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}
export function decimal(value: unknown): number | null {
  if (typeof value !== "string" || !/^[-+]?\d+(\.\d+)?$/.test(value))
    return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}
export function label(value: unknown) {
  return typeof value === "string"
    ? value.replaceAll("_", " ")
    : "Not recorded";
}
export function object(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}
export function text(value: unknown, fallback = "—"): string {
  return typeof value === "string" || typeof value === "number"
    ? String(value)
    : fallback;
}
export function list(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}
