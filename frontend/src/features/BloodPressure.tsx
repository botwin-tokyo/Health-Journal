import { lazy, Suspense } from "react";
import { useInfiniteQuery } from "@tanstack/react-query";
import { usePage } from "../app/Shell";
import { records, useSession } from "../api/hooks";
import { api } from "../api/transport";
import { Card, Empty, LoadState, Badge } from "../components/ui";
import { object, shiftDate, text } from "../lib/display";
import { bloodPressureReadings, monitorFlags } from "../lib/bloodPressure";
const Chart = lazy(() => import("../components/ChartFrame"));
export default function BloodPressure() {
  const { date, range, setRange } = usePage();
  const from = shiftDate(date, 1 - range);
  const { session, generation, preview } = useSession();
  const query = useInfiniteQuery({
    queryKey: [
      session?.account_id,
      session?.context.owner_id,
      session?.context.grant_id,
      preview,
      session?.permission_epoch,
      generation,
      "blood-pressure",
      from,
      date,
    ],
    initialPageParam: "",
    enabled: !!session,
    queryFn: async ({ pageParam, signal }) =>
      object(
        await api(
          `/api/v1/blood-pressure?from=${from}&to=${date}${pageParam ? `&cursor=${encodeURIComponent(pageParam)}` : ""}`,
          { signal },
        ),
      ),
    getNextPageParam: (page) =>
      typeof page.cursor === "string" && page.cursor ? page.cursor : undefined,
    refetchInterval: 15000,
  });
  const unique = new Map(
    (query.data?.pages.flatMap((page) => records(page.items)) || []).map(
      (row) => [row.id, row],
    ),
  );
  const readings = bloodPressureReadings([...unique.values()]);
  const charted = readings.filter((row) => row.eligible);
  return (
    <div className="stack">
      <label>History range <select value={range} onChange={event => setRange(Number(event.target.value))}>
        {[7, 28, 90, 365].map(days => <option key={days} value={days}>{days} days</option>)}
      </select></label>
      <p className="muted">
        {from} to {date} | Synced from mobile app
      </p>
      <LoadState loading={query.isPending} error={query.error}>
        <Card title="Saved measurements">
          {!readings.length && (
            <Empty>
              No blood-pressure readings received in this date range. Sync your
              monitor to mobile app; its midnight upload brings saved readings
              here.
            </Empty>
          )}
          <p className="small muted">
            Dates shown retain the recorded time and offset. Unverified dates
            are labelled as reception times and excluded from trends. Monitor
            flags remain attached to each reading.
          </p>
          {query.hasNextPage && (
            <p role="status">
              Showing part of this range. Load older readings to extend the
              charts and history.
            </p>
          )}
          <div className="tableWrap">
            <table style={{ minWidth: 680 }}>
              <caption className="srOnly">
                Saved blood-pressure measurements
              </caption>
              <thead>
                <tr>
                  <th scope="col">Time</th>
                  <th scope="col">Pressure (mmHg)</th>
                  <th scope="col">Pulse (bpm)</th>
                  <th scope="col">Source and quality</th>
                </tr>
              </thead>
              <tbody>
                {[...readings].reverse().map((row) => (
                  <tr key={row.id}>
                    <td>
                      {row.verified ? row.at : `Received ${row.at}`}
                      <br />
                      {!row.verified && (
                        <Badge>Measurement time unverified</Badge>
                      )}
                    </td>
                    <td>
                      {row.systolic ?? "Not supplied"} /{" "}
                      {row.diastolic ?? "Not supplied"}
                    </td>
                    <td>{row.pulse ?? "Not supplied"}</td>
                    <td>
                      {row.device}
                      <br />
                      {monitorFlags(row).join("; ")}
                      {!row.eligible && row.verified && (
                        <Badge>Source qualification requires review</Badge>
                      )}
                      <details>
                        <summary>Reading details</summary>
                        {row.rows.map((item) => (
                          <div key={item.id}>
                            <p>{text(item.data.qualification)}</p>
                            <p className="small muted">
                              Saved revision {item.version}
                            </p>
                            <pre
                              style={{
                                whiteSpace: "pre-wrap",
                                overflowWrap: "anywhere",
                                maxHeight: 240,
                                overflow: "auto",
                              }}
                            >
                              {JSON.stringify(
                                item.data.native_record || item.data,
                                null,
                                2,
                              )}
                            </pre>
                          </div>
                        ))}
                      </details>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {query.hasNextPage && (
            <button
              disabled={query.isFetchingNextPage}
              onClick={() => void query.fetchNextPage()}
            >
              {query.isFetchingNextPage ? "Loading..." : "Load older readings"}
            </button>
          )}
        </Card>
        <Suspense fallback={<p>Loading charts...</p>}>
          <div className="split">
            {(["systolic", "diastolic"] as const).map((field) => (
              <Chart
                key={field}
                title={
                  field === "systolic"
                    ? "Systolic pressure"
                    : "Diastolic pressure"
                }
                unit="mmHg"
                source="Verified measurement times | monitor readings"
                points={charted
                  .filter((row) => row[field] !== undefined)
                  .map((row) => ({
                    x: row.at,
                    value: row[field]!,
                    original: String(row[field]),
                    revision: row.id,
                  }))}
              />
            ))}
          </div>
          <Chart
            title="Monitor pulse"
            unit="bpm"
            source="Verified measurement times | monitor readings"
            points={charted
              .filter((row) => row.pulse !== undefined)
              .map((row) => ({
                x: row.at,
                value: row.pulse!,
                original: String(row.pulse),
                revision: row.id,
              }))}
          />
        </Suspense>
      </LoadState>
    </div>
  );
}
