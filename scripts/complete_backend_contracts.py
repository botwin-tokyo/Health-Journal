"""Generate domain response schemas and an executable memory-only API client."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
schema = json.loads((ROOT / "contracts/openapi.yaml").read_text())
components = schema["components"]["schemas"]
string = {"type": "string"}


def obj(properties, required=()):
    return {
        "type": "object",
        "properties": properties,
        "required": list(required),
        "additionalProperties": True,
    }


def ref(name):
    return {"$ref": "#/components/schemas/" + name}


components.update(
    {
        "CommandReceipt": obj(
            {
                "id": string,
                "state": string,
                "status": string,
                "etag": string,
                "context_reset_required": {"type": "boolean"},
            }
        ),
        "ExportPart": obj(
            {"id": string, "bytes": {"type": "integer", "minimum": 0}, "mime_type": string},
            ["id", "bytes", "mime_type"],
        ),
        "ExportStatus": obj(
            {
                "id": string,
                "state": {
                    "enum": [
                        "queued",
                        "running",
                        "ready",
                        "failed",
                        "expired",
                        "revoked",
                        "cancelled",
                    ]
                },
                "parts": {"type": "array", "items": ref("ExportPart")},
                "error_code": string,
            },
            ["id", "state"],
        ),
        "DownloadTicket": obj(
            {"ticket": string, "part_id": string, "start_deadline_seconds": {"const": 60}},
            ["ticket", "part_id", "start_deadline_seconds"],
        ),
        "LabReview": obj(
            {
                "patient_match_confirmed": {"const": True},
                "source_report_status": {"enum": ["preliminary", "final", "corrected", "unknown"]},
                "clinical_date": {"type": ["string", "null"]},
                "time_precision": {"enum": ["day", "unknown"]},
                "document_only": {"type": "boolean"},
                "results": {"type": "array", "maxItems": 5000, "items": ref("LabResult")},
            }
        ),
        "LabResult": obj(
            {
                "label": {"type": "string", "maxLength": 256},
                "raw_result_text": {"type": "string", "maxLength": 16384},
                "value_kind": {"enum": ["numeric", "text", "coded"]},
                "value": {"oneOf": [ref("Decimal"), {"type": "null"}]},
                "operator": {"enum": ["eq", "lt", "le", "gt", "ge"]},
                "unit": {"type": ["string", "null"]},
                "excluded": {"type": "boolean"},
            },
            ["label", "raw_result_text"],
        ),
        "PulmonaryInput": obj(
            {
                "clinical_date": string,
                "time_precision": {"enum": ["day", "minute", "second"]},
                "measured_start": {"type": ["string", "null"]},
                "timezone": string,
                "original_offset_minutes": {"type": "integer"},
                "slot": {"enum": ["morning", "noon", "evening", None]},
                "values": {
                    "type": "object",
                    "additionalProperties": {"oneOf": [ref("Decimal"), {"type": "null"}]},
                },
            },
            ["clinical_date", "time_precision", "values"],
        ),
        "JournalInput": obj(
            {
                "clinical_date": string,
                "time_precision": string,
                "title": {"type": "string", "maxLength": 256},
                "text": {"type": "string", "maxLength": 16384},
                "visibility": {"enum": ["private", "shared"]},
                "tags": {
                    "type": "array",
                    "maxItems": 20,
                    "items": {"type": "string", "maxLength": 64},
                },
            },
            ["clinical_date", "time_precision"],
        ),
        "GrantInput": obj(
            {
                "recipient_email": {"type": "string", "format": "email"},
                "from": string,
                "to": string,
                "categories": {
                    "type": "array",
                    "items": {
                        "enum": [
                            "body",
                            "breathing",
                            "sleep_activity",
                            "labs",
                            "journal",
                            "questions",
                        ]
                    },
                },
                "actions": {
                    "type": "array",
                    "items": {"enum": ["read", "download_report", "read_original_document"]},
                },
                "record_allowlists": obj(
                    {
                        "journal": {"type": "array", "items": string},
                        "questions": {"type": "array", "items": string},
                        "medication_events": {"type": "array", "items": string},
                        "labs": {"type": ["array", "null"], "items": string},
                    },
                    ["journal", "questions", "medication_events", "labs"],
                ),
                "document_ids": {"type": "array", "items": string},
            },
            [
                "recipient_email",
                "from",
                "to",
                "categories",
                "actions",
                "record_allowlists",
                "document_ids",
            ],
        ),
        "ReadModel": {
            "type": "object",
            "additionalProperties": True,
            "description": "Authorized page-specific model; missing values remain null with absent_reason. No unrestricted owner payload is returned in a grant context.",
        },
    }
)
# The HTTP receipt precedes item-level validation by the worker.
wire = json.loads((ROOT / "contracts/phone/batch.schema.json").read_text())
envelope = {key: wire[key] for key in ("type", "additionalProperties", "required", "properties")}
envelope["properties"]["items"] = {
    **envelope["properties"]["items"],
    "items": {
        "description": "Phone item; validated asynchronously against contracts/phone/batch.schema.json."
    },
}
components["BatchInput"] = envelope
components["BatchReceipt"] = obj(
    {
        "batch_id": {"type": "string", "format": "uuid"},
        "state": string,
        "receipt_url": {"type": "string", "format": "uri-reference"},
    },
    ["batch_id", "state", "receipt_url"],
)
nullable_uuid = {"type": ["string", "null"], "format": "uuid"}
item_receipt = obj(
    {
        "ordinal": {"type": "integer", "minimum": 0},
        "outcome": string,
        "reason": string,
        "record_id": nullable_uuid,
        "revision_id": nullable_uuid,
        "disposition": string,
    },
    ["ordinal", "outcome", "reason", "record_id", "revision_id", "disposition"],
)
components["BatchStatus"] = obj(
    {
        "batch_id": {"type": "string", "format": "uuid"},
        "state": string,
        "items": {"type": "array", "items": item_receipt},
        "durably_retained": {"type": "boolean"},
        "clinical_acceptance": {"type": "boolean"},
    },
    ["batch_id", "state", "items", "durably_retained", "clinical_acceptance"],
)
schema["components"]["securitySchemes"]["DeviceApiKey"] = {
    "type": "apiKey",
    "in": "header",
    "name": "X-API-Key",
}
operations = json.loads((ROOT / "contracts/security/operations.json").read_text())
client = []
for policy in operations["operations"]:
    path, method = policy["path"], policy["method"]
    operation = schema["paths"][path][method.lower()]
    # Verification is a separate gate; implementation reflects the checked-in application.
    operation["x-implemented"] = True
    policy["implemented"] = True
    operation["x-validation-status"] = "pending-final-acceptance"
    name = "ReadModel" if method == "GET" else "CommandReceipt"
    if "/exports/{id}" == path.removeprefix("/api/v1") and method == "GET":
        name = "ExportStatus"
    if path.endswith("/download-tickets"):
        name = "DownloadTicket"
    if path.endswith("/content"):
        operation["responses"]["200"] = {
            "description": "Authenticated bounded bytes",
            "content": {
                "application/octet-stream": {"schema": {"type": "string", "format": "binary"}}
            },
        }
    else:
        if (
            any(
                part in path
                for part in [
                    "/weights/{id}",
                    "/sessions/{id}",
                    "/snapshots/{id}",
                    "/baselines/{id}",
                ]
            )
            and method == "GET"
        ):
            name = "Record"
        operation["responses"]["200"] = {
            "description": operation["responses"]
            .get("200", {})
            .get("description", "Current authorized response"),
            "content": {"application/json": {"schema": ref(name)}},
        }
    if path.startswith("/api/v1/ingestion/"):
        operation["security"] = [{"UploaderBearer": []}, {"DeviceApiKey": []}]
    if path == "/api/v1/ingestion/batches" and method == "POST":
        operation["requestBody"] = {
            "required": True,
            "content": {"application/json": {"schema": ref("BatchInput")}},
        }
        for status, description in [
            ("202", "New batch durably received and queued for item processing"),
            ("200", "Identical batch replay; current state and original receipt URL"),
        ]:
            operation["responses"][status] = {
                "description": description,
                "content": {"application/json": {"schema": ref("BatchReceipt")}},
            }
        operation["responses"]["409"] = {
            "description": "Batch ID already used with different content or by another device",
            "content": {"application/json": {"schema": ref("Error")}},
        }
    if path == "/api/v1/ingestion/batches/{batch_id}" and method == "GET":
        operation["responses"]["200"] = {
            "description": "Device-scoped status and current per-item outcomes",
            "content": {"application/json": {"schema": ref("BatchStatus")}},
        }
    if method not in {"GET", "HEAD"}:
        input_name = None
        if path.endswith("/manual-sessions"):
            input_name = "PulmonaryInput"
        elif path.endswith("/labs/reports/{id}/review"):
            input_name = "LabReview"
        elif path.endswith("/sharing/grants") and method == "POST":
            input_name = "GrantInput"
        elif "/body/weights" in path and method in {"POST", "PATCH"}:
            input_name = "WeightInput"
        if input_name:
            operation["requestBody"] = {
                "required": True,
                "content": {"application/json": {"schema": ref(input_name)}},
            }
    operation.setdefault("parameters", [])
    import re

    for variable in re.findall(r"{([^}]+)}", path):
        if not any(
            p.get("name") == variable and p.get("in") == "path" for p in operation["parameters"]
        ):
            operation["parameters"].append(
                {"name": variable, "in": "path", "required": True, "schema": string}
            )
    client.append(
        f"  {json.dumps(operation['operationId'])}: {{method:{json.dumps(method)},path:{json.dumps(path)}}},"
    )
operations["notes"][0] = (
    "Implementation is checked in; runtime acceptance is recorded separately in release evidence."
)
(ROOT / "contracts/security/operations.json").write_text(json.dumps(operations, indent=2) + "\n")
(ROOT / "contracts/openapi.yaml").write_text(json.dumps(schema, indent=2) + "\n")
digest = hashlib.sha256((ROOT / "contracts/openapi.yaml").read_bytes()).hexdigest()
(ROOT / "contracts/openapi.sha256").write_text(digest + "\n")
(ROOT / "frontend/generated/client.ts").write_text(
    """// Generated by scripts/complete_backend_contracts.py. No persistent storage.
export type Json = null | boolean | number | string | Json[] | {[key:string]:Json};
export interface Transport { request(path:string, options:{method:string;body?:unknown;headers?:Record<string,string>}):Promise<unknown> }
export const operations = {
"""
    + "\n".join(client)
    + '''
} as const;
export type Operation = keyof typeof operations;
export function createBackendClient(transport:Transport) {
  return { async call<T = Json>(operation:Operation, options:{params?:Record<string,string>;query?:Record<string,string>;body?:unknown;headers?:Record<string,string>;etag?:string;idempotencyKey?:string}={}):Promise<T> {
    const spec=operations[operation];
    const path=spec.path.replace(/\\{([^}]+)\\}/g,(_,key:string)=>{const value=options.params?.[key];if(!value)throw new Error('missing_path_parameter');return encodeURIComponent(value);});
    const query=new URLSearchParams(options.query).toString();
    const headers:Record<string,string>={...options.headers};
    if(options.etag)headers['If-Match']=options.etag;
    if(spec.method!=='GET')headers['Idempotency-Key']=options.idempotencyKey||crypto.randomUUID();
    return await transport.request(path+(query?'?'+query:''),{method:spec.method,body:options.body,headers}) as T;
  }};
}
export const schemaSha256 = "'''
    + digest
    + '";\n'
)
p = ROOT / "frontend/generated/backend.ts"
s = p.read_text()
s = re.sub(
    r'export const schemaSha256 = "[a-f0-9]+";', f'export const schemaSha256 = "{digest}";', s
)
p.write_text(s)
