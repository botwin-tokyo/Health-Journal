import { useSyncExternalStore } from "react";
import { useQuery } from "@tanstack/react-query";
import { z } from "zod";
import { api, authStore } from "./transport";
export const recordSchema = z
  .object({
    id: z.string(),
    revision_id: z.string(),
    kind: z.string(),
    version: z.number(),
    etag: z.string(),
    clinical_date: z.string().nullable().optional(),
    received_at: z.string().optional(),
    data: z.record(z.string(), z.unknown()),
  })
  .passthrough();
export type ClinicalRecord = z.infer<typeof recordSchema>;
export function records(value: unknown): ClinicalRecord[] {
  if (value === undefined || value === null) return [];
  const result = z.array(recordSchema).safeParse(value);
  if (!result.success) throw Error("Unexpected record format");
  return result.data;
}
export function useSession() {
  return useSyncExternalStore(authStore.subscribe, authStore.snapshot);
}
export function useApi(path: string | null, poll: boolean | number = false) {
  const { session, generation, preview } = useSession();
  return useQuery({
    queryKey: [
      session?.account_id,
      session?.context.owner_id,
      session?.context.grant_id,
      preview,
      session?.permission_epoch,
      generation,
      path,
    ],
    queryFn: async ({ signal }) =>
      z.record(z.string(), z.unknown()).parse(await api(path!, { signal })),
    enabled: !!session && !!path,
    refetchInterval: typeof poll === "number" ? poll : poll
      ? (query) =>
          [
            "queued",
            "processing",
            "running",
            "extracting",
            "requesting",
            "syncing",
          ].includes(
            String(
              query.state.data?.parse_state ||
                query.state.data?.state ||
                (Array.isArray(query.state.data?.requests)
                  ? query.state.data.requests[0]?.state || "idle"
                  : "queued"),
            ),
          )
            ? 3000
            : false
      : false,
  });
}
