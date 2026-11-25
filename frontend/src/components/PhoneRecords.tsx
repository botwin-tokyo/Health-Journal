import { useState } from "react";
import { records, useApi } from "../api/hooks";
import { api } from "../api/transport";
import { Card, Badge, LoadState, Empty } from "./ui";
import { label, text } from "../lib/display";

function assetIds(value: unknown): string[] {
  if (Array.isArray(value)) return value.flatMap(assetIds);
  if (value && typeof value === "object") return Object.entries(value).flatMap(([key, child]) =>
    key === "asset_ids" && Array.isArray(child) ? child.filter((v): v is string => typeof v === "string") : assetIds(child));
  return [];
}

export default function PhoneRecords({date, domain}: {date: string; domain: "body" | "breathing" | "sleep"}) {
  const [paging, setPaging] = useState({date, cursor: ""});
  const [error, setError] = useState("");
  const cursor = paging.date === date ? paging.cursor : "";
  const query = useApi(`/api/v1/phone/records?domain=${domain}&from=${date}&to=${date}${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`, cursor ? false : 15000);
  async function download(recordId: string, assetId: string) {
    try {
      setError("");
      const bytes = await api(`/api/v1/phone/records/${recordId}/assets/${assetId}`, {binary: true});
      const url = URL.createObjectURL(new Blob([bytes as ArrayBuffer], {type: "application/octet-stream"}));
      const link = document.createElement("a"); link.href=url; link.download="phone-evidence.bin"; link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch { setError("The evidence could not be downloaded. Refresh the record and try again."); }
  }
  return <Card title="Received phone records">
    <LoadState loading={query.isPending} error={query.error}>
      {!records(query.data?.items).length && <Empty>No phone records received for this date.</Empty>}
      {records(query.data?.items).map(row => <details key={row.id} className="stack">
        <summary>
          <strong>{label(row.data.metric_id || row.data.title || row.data.activity || row.data.source_kind || row.kind)}</strong>
          {" · "}{text(row.data.value, "")}{" "}{text(row.data.unit, "")}{" · "}
          <Badge>{row.data.clinical_eligible === false ? "Source evidence" : "Recorded"}</Badge>
        </summary>
        <p className="small muted">{label(row.data.source_type)} · {text(row.data.measured_start, row.clinical_date || "")}</p>
        {row.data.clinical_eligible === false && <p>{Array.isArray(row.data.evidence_reasons) ? row.data.evidence_reasons.map(label).join(", ") : "Retained source evidence"}. Preserved separately from clinical summaries.</p>}
        <pre style={{whiteSpace:"pre-wrap",overflowWrap:"anywhere",maxHeight:480,overflow:"auto"}}>{JSON.stringify(row.data, null, 2)}</pre>
        {[...new Set(assetIds(row.data))].map(id => <button key={id} onClick={() => download(row.id, id)}>Download source evidence {id.slice(0, 8)}</button>)}
      </details>)}
      {error && <p role="alert">{error}</p>}
      <div className="row">
        {cursor && <button onClick={() => setPaging({date, cursor:""})}>First phone records</button>}
        {query.data?.cursor ? <button onClick={() => setPaging({date,cursor:text(query.data?.cursor, "")})}>Next phone records</button> : null}
      </div>
    </LoadState>
  </Card>;
}
