import { useEffect, useRef, useState } from "react";
import {
  getDocument,
  GlobalWorkerOptions,
  type PDFDocumentProxy,
  type RenderTask,
} from "pdfjs-dist";
import workerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import { api, registerCleanup } from "../api/transport";
import { ErrorBox } from "./ui";
GlobalWorkerOptions.workerSrc = workerUrl;
export default function DocumentViewer({ documentId }: { documentId: string }) {
  const canvas = useRef<HTMLCanvasElement>(null),
    document = useRef<PDFDocumentProxy | null>(null),
    render = useRef<RenderTask | null>(null);
  const [page, setPage] = useState(1),
    [count, setCount] = useState(0),
    [content, setContent] = useState(""),
    [error, setError] = useState<unknown>(null),
    [version, setVersion] = useState(0);
  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();
    let loading: ReturnType<typeof getDocument> | null = null;
    const clear = () => {
      cancelled = true;
      controller.abort();
      render.current?.cancel();
      void loading?.destroy();
      void document.current?.destroy();
      document.current = null;
      if (canvas.current) {
        canvas.current.width = 0;
        canvas.current.height = 0;
      }
    };
    const unregister = registerCleanup(clear);
    void api("/api/v1/documents/" + documentId + "/content", {
      binary: true,
      signal: controller.signal,
    })
      .then(async (value) => {
        if (cancelled) return;
        loading = getDocument({
          data: new Uint8Array(value as ArrayBuffer),
          enableXfa: false,
          useSystemFonts: false,
          cMapUrl: "/pdf-assets/cmaps/",
          cMapPacked: true,
          standardFontDataUrl: "/pdf-assets/standard_fonts/",
          wasmUrl: "/pdf-assets/wasm/",
        });
        const loaded = await loading.promise;
        if (cancelled) {
          await loaded.destroy();
          return;
        }
        document.current = loaded;
        setCount(loaded.numPages);
        setPage(1);
        setVersion((v) => v + 1);
      })
      .catch((e) => {
        if (!cancelled) setError(e);
      });
    return () => {
      unregister();
      clear();
    };
  }, [documentId]);
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      if (!document.current || !canvas.current) return;
      const pdfPage = await document.current.getPage(page);
      if (cancelled || !canvas.current) return;
      const viewport = pdfPage.getViewport({ scale: 1.25 });
      canvas.current.width = viewport.width;
      canvas.current.height = viewport.height;
      render.current = pdfPage.render({ canvas: canvas.current, viewport });
      await render.current.promise;
      const text = await pdfPage.getTextContent();
      if (!cancelled)
        setContent(
          text.items.map((item) => ("str" in item ? item.str : "")).join(" "),
        );
    })().catch((e) => {
      if (!cancelled && e?.name !== "RenderingCancelledException") setError(e);
    });
    return () => {
      cancelled = true;
      render.current?.cancel();
    };
  }, [page, version]);
  return (
    <div className="stack">
      <ErrorBox error={error} />
      <div className="row between">
        <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
          Previous page
        </button>
        <span>
          {page} / {count || "—"}
        </span>
        <button disabled={page >= count} onClick={() => setPage((p) => p + 1)}>
          Next page
        </button>
      </div>
      <canvas
        ref={canvas}
        aria-label={"Original report page " + page}
        style={{
          width: "100%",
          height: "auto",
          border: "1px solid var(--border)",
        }}
      />
      <details>
        <summary>Accessible extracted page text</summary>
        <p className="note small">
          {content ||
            "This scanned page has no embedded text. Use the reviewed results or local OCR extraction."}
        </p>
      </details>
      <p className="small muted">
        Original document · no scripts, forms or external links are activated.
      </p>
    </div>
  );
}
