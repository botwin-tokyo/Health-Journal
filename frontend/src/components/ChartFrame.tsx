import { useState } from "react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  BarChart,
  Bar,
} from "recharts";
import { Card, Empty } from "./ui";
export type Point = {
  x: string | number;
  value: number | null;
  original: string;
  revision?: string;
};
export default function ChartFrame({
  title,
  points,
  unit,
  source,
  reference,
  bars = false,
  numericX = false,
}: {
  title: string;
  points: Point[];
  unit: string;
  source: string;
  reference?: number | null;
  bars?: boolean;
  numericX?: boolean;
}) {
  const dates =
    !numericX &&
    points.length > 0 &&
    points.every(
      (p) => typeof p.x === "string" && /^\d{4}-\d{2}-\d{2}$/.test(p.x),
    );
  const plotted = dates
    ? points.flatMap((point, index) => {
        const x = Date.parse(String(point.x) + "T00:00:00Z");
        const previous = index
          ? Date.parse(String(points[index - 1].x) + "T00:00:00Z")
          : x;
        return [
          ...(x - previous > 86400000
            ? [{ x: previous + 86400000, value: null, original: "Unavailable" }]
            : []),
          { ...point, x },
        ];
      })
    : points;
  const [table, setTable] = useState(false);
  const chartChildren = (
    <>
      <CartesianGrid stroke="var(--border)" />
      <XAxis
        dataKey="x"
        type={numericX || dates ? "number" : "category"}
        domain={numericX || dates ? ["dataMin", "dataMax"] : undefined}
        tickFormatter={
          dates
            ? (value) => new Date(Number(value)).toISOString().slice(5, 10)
            : undefined
        }
        minTickGap={32}
        tick={{ fontSize: 12, fill: "var(--muted)" }}
      />
      <YAxis
        domain={bars ? [0, "auto"] : ["auto", "auto"]}
        width={48}
        tick={{ fontSize: 12, fill: "var(--muted)" }}
      />
      <Tooltip
        contentStyle={{ borderColor: "var(--control)", background: "var(--surface)", color: "var(--text)", borderRadius: 6 }}
        formatter={(_value, _name, item) => [
          String(item.payload.original) + " " + unit,
          title,
        ]}
      />
      {reference != null && (
        <ReferenceLine
          y={reference}
          stroke="var(--muted)"
          strokeDasharray="5 5"
          label="Reference"
        />
      )}
    </>
  );
  return (
    <Card title={title}>
      <div className="row between small muted">
        <span>{source}</span>
        <span>{unit}</span>
      </div>
      {!points.length ? (
        <Empty>No eligible readings in this selection.</Empty>
      ) : (
        <>
          <div
            className="chart"
            role="img"
            aria-label={
              title + ". An equivalent data table is available below."
            }
          >
            <ResponsiveContainer width="100%" height="100%">
              {bars ? (
                <BarChart data={plotted} accessibilityLayer>
                  {chartChildren}
                  <Bar
                    dataKey="value"
                    fill="var(--muted)"
                    isAnimationActive={false}
                  />
                </BarChart>
              ) : (
                <LineChart data={plotted} accessibilityLayer>
                  {chartChildren}
                  <Line
                    dataKey="value"
                    stroke="var(--text)"
                    strokeWidth={2}
                    type="linear"
                    dot={{ r: 3, fill: "var(--text)" }}
                    activeDot={{ fill: "var(--accent)", r: 5 }}
                    connectNulls={false}
                    isAnimationActive={false}
                  />
                </LineChart>
              )}
            </ResponsiveContainer>
          </div>
          <p className="small muted">
            {bars
              ? "Bars start at zero."
              : "Axis scaled to observed values. Missing readings remain gaps."}
          </p>
        </>
      )}
      <button
        type="button"
        className="quiet"
        aria-expanded={table}
        onClick={() => setTable(!table)}
      >
        {table ? "Hide" : "Show"} data table
      </button>
      {table && (
        <div className="tableWrap">
          <table>
            <caption className="srOnly">{title} readings</caption>
            <thead>
              <tr>
                <th scope="col">Date / coordinate</th>
                <th scope="col">Value ({unit})</th>
              </tr>
            </thead>
            <tbody>
              {points.map((point, i) => (
                <tr key={point.revision || i}>
                  <td>{point.x}</td>
                  <td>
                    {point.value === null ? "Unavailable" : point.original}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
