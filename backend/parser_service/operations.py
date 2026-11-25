import csv
import html
import io
import json
import os
import signal
import subprocess
import tempfile
from decimal import Decimal, InvalidOperation
from pathlib import Path

MAX_TEXT = 2 * 1024 * 1024


def command(argv, timeout=300):
    process = subprocess.Popen(
        argv,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "HOME": "/work"},
        start_new_session=False,
    )
    try:
        output, _ = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        process.wait()
        raise ValueError("parser_timeout") from None
    if process.returncode or len(output) > MAX_TEXT:
        raise ValueError("invalid_document")
    return output


def parse_pdf(payload):
    from pypdf import PdfReader

    if not payload.startswith(b"%PDF-"):
        raise ValueError("invalid_document")
    with tempfile.TemporaryDirectory(dir="/work") as temporary:
        source = Path(temporary) / "input.pdf"
        source.write_bytes(payload)
        reader = PdfReader(io.BytesIO(payload), strict=True)
        if reader.is_encrypted or not 1 <= len(reader.pages) <= 100:
            raise ValueError("unsupported_document")
        root = reader.trailer["/Root"].get_object()
        names = root.get("/Names", {})
        if hasattr(names, "get_object"):
            names = names.get_object()
        if any(key in root for key in ("/OpenAction", "/AA")) or any(
            key in names for key in ("/JavaScript", "/EmbeddedFiles")
        ):
            raise ValueError("active_document_not_supported")
        for page in reader.pages:
            if "/AA" in page or page.get("/Annots"):
                raise ValueError("active_document_not_supported")
            if (
                float(page.mediabox.width) * float(page.mediabox.height) * (300 / 72) ** 2
                > 30000000
            ):
                raise ValueError("page_too_large")
        command(["/usr/bin/qpdf", "--check", str(source)])
        text = []
        total = 0
        for page in reader.pages:
            value = page.extract_text() or ""
            total += len(value.encode("utf-8"))
            if total > MAX_TEXT:
                raise ValueError("extracted_text_too_large")
            text.append(value)
        engine = "pypdf"
        if any(not value.strip() for value in text):
            engine = "ocrmypdf-tesseract"
            target = Path(temporary) / "ocr.pdf"
            command(
                [
                    "/usr/bin/ocrmypdf",
                    "--skip-text",
                    "--jobs",
                    "1",
                    "--max-image-mpixels",
                    "30",
                    "--tesseract-timeout",
                    "240",
                    "--sidecar",
                    str(Path(temporary) / "text.txt"),
                    str(source),
                    str(target),
                ]
            )
            with (Path(temporary) / "text.txt").open("rb") as stream:
                raw = stream.read(MAX_TEXT + 1)
            if len(raw) > MAX_TEXT:
                raise ValueError("extracted_text_too_large")
            text = [page.extract_text() or "" for page in PdfReader(str(target), strict=True).pages]
            if sum(len(value.encode()) for value in text) > MAX_TEXT:
                raise ValueError("extracted_text_too_large")
        return json.dumps(
            {
                "state": "requires_review",
                "pages": len(reader.pages),
                "text": text,
                "extraction_engine": engine,
                "extraction_schema": "text-pages-v1",
                "source_pages": [
                    {"page": index + 1, "text": value, "coordinates": None}
                    for index, value in enumerate(text)
                ],
            }
        ).encode()


def parse_csv(payload):
    if len(payload) > 5 * 1024 * 1024:
        raise ValueError("csv_too_large")
    rows = []
    for index, row in enumerate(csv.reader(io.StringIO(payload.decode("utf-8-sig")))):
        if index >= 100000 or len(row) > 100:
            raise ValueError("csv_too_large")
        rows.append(row)
    result = json.dumps({"state": "requires_review", "rows": rows}).encode()
    if len(result) > MAX_TEXT:
        raise ValueError("extracted_text_too_large")
    return result


def render_report(payload):
    from pypdf import PdfReader
    from weasyprint import HTML

    snapshot = json.loads(payload)
    template = snapshot.get("template")
    if (
        template not in {"appointment-v1", "appointment-v2"}
        or not isinstance(snapshot.get("sections"), list)
        or len(snapshot["sections"]) > 100
    ):
        raise ValueError("invalid_report_snapshot")
    if template == "appointment-v1" and set(snapshot) != {"template", "sections"}:
        raise ValueError("invalid_report_snapshot")
    if len(payload) > 25 * 1024 * 1024:
        raise ValueError("report_scope_too_large")
    sections = []
    for section in snapshot["sections"]:
        if not isinstance(section, dict) or not {"heading", "text"} <= set(section):
            raise ValueError("invalid_report_snapshot")
        content = "<pre>" + html.escape(str(section["text"])) + "</pre>"
        if template == "appointment-v2":
            rows = []
            for key, value in section.get("data", {}).items():
                rendered = (
                    json.dumps(value, ensure_ascii=False, sort_keys=True)
                    if isinstance(value, (dict, list))
                    else "Not recorded"
                    if value is None
                    else str(value)
                )
                rows.append(
                    "<tr><th>"
                    + html.escape(key.replace("_", " "))
                    + "</th><td>"
                    + html.escape(rendered)
                    + "</td></tr>"
                )
            content = (
                "<p>"
                + html.escape(str(section.get("clinical_date") or "Collection date unavailable"))
                + "</p><table>"
                + "".join(rows)
                + "</table>"
            )
        sections.append(
            "<section><h2>"
            + html.escape(str(section["heading"]))
            + "</h2>"
            + content
            + "</section>"
        )
    title = html.escape(str(snapshot.get("title", "Health report")))
    header = "<h1>" + title + "</h1><p>Personal tracking report. No diagnostic interpretation.</p>"
    if template == "appointment-v2":
        header += (
            "<p>Generated "
            + html.escape(str(snapshot.get("generated_at")))
            + " · Measured through "
            + html.escape(str(snapshot.get("measured_through") or "Not recorded"))
            + "</p>"
        )
    style = "<style>@page {size:A4;margin:18mm}body{font-family:DejaVu Sans;font-size:10pt}h1{font-size:20pt}h2{border-bottom:1px solid #d22}table{width:100%;border-collapse:collapse}th,td{text-align:left;vertical-align:top;border-bottom:1px solid #ddd;padding:4px;overflow-wrap:anywhere}th{width:30%}pre{white-space:pre-wrap;overflow-wrap:anywhere}section{break-before:auto}</style>"

    def fetch(url, *args, **kwargs):
        raise ValueError("external_report_resource_denied")

    from .charts import frozen_charts

    sections.append(frozen_charts(snapshot["sections"]))
    result = HTML(
        string="<!doctype html><title>" + title + "</title>" + style + header + "".join(sections),
        url_fetcher=fetch,
    ).write_pdf()
    appendices = snapshot.get("appendices", [])
    if appendices:
        import base64

        from pypdf import PdfWriter

        writer = PdfWriter()
        writer.append(io.BytesIO(result))
        for appendix in appendices:
            original = base64.b64decode(appendix["pdf_base64"], validate=True)
            reader = PdfReader(io.BytesIO(original), strict=True)
            if reader.is_encrypted or len(writer.pages) + len(reader.pages) > 100:
                raise ValueError("report_scope_too_large")
            writer.append(reader, import_outline=False)
        stream = io.BytesIO()
        writer.write(stream)
        result = stream.getvalue()
    if len(result) > 25 * 1024 * 1024 or len(PdfReader(io.BytesIO(result)).pages) > 100:
        raise ValueError("report_scope_too_large")
    return result


def csv_cell(value, numeric=False):
    if numeric:
        try:
            number = Decimal(str(value))
            if not number.is_finite():
                raise InvalidOperation
            return format(number, "f")
        except InvalidOperation:
            raise ValueError("invalid_numeric_cell") from None
    text = str(value)
    return "'" + text if text.startswith(("=", "+", "-", "@", "\t", "\r")) else text
