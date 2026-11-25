"""Build wire schemas/client declarations; validation belongs to the final gate."""

import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
path = root / "contracts/openapi.yaml"
schema = json.loads(path.read_text())
schema["info"] = {"title": "Health Journal backend contract", "version": "0.1.0"}


def obj(properties, required=()):
    return {
        "type": "object",
        "properties": properties,
        "required": list(required),
        "additionalProperties": False,
    }


string = {"type": "string"}
nullable = {"type": ["string", "null"]}
components = schema.setdefault("components", {}).setdefault("schemas", {})
components.update(
    {
        "Decimal": {
            "type": "string",
            "pattern": r"^-?(0|[1-9][0-9]*)(\.[0-9]{1,18})?$",
            "maxLength": 56,
        },
        "Error": obj(
            {
                "error": obj(
                    {
                        "code": string,
                        "message": string,
                        "field_errors": {
                            "type": "array",
                            "items": obj({"path": string, "code": string, "message": string}),
                        },
                        "request_id": nullable,
                        "retryable": {"type": "boolean"},
                    },
                    ["code", "message", "field_errors", "retryable"],
                )
            },
            ["error"],
        ),
        "Record": obj(
            {
                "id": {"type": "string", "format": "uuid"},
                "revision_id": {"type": "string", "format": "uuid"},
                "kind": string,
                "version": {"type": "integer", "minimum": 1},
                "etag": string,
                "clinical_date": nullable,
                "received_at": {"type": "string", "format": "date-time"},
                "data": {"type": "object"},
            },
            ["id", "revision_id", "kind", "version", "etag", "data"],
        ),
        "Page": obj(
            {
                "items": {"type": "array", "items": {"$ref": "#/components/schemas/Record"}},
                "cursor": nullable,
            },
            ["items", "cursor"],
        ),
        "WeightInput": obj(
            {
                "value": {"$ref": "#/components/schemas/Decimal"},
                "unit": {"enum": ["kg", "lb"]},
                "clinical_date": {"type": "string", "format": "date"},
                "time_precision": {"enum": ["day", "minute", "second"]},
                "measured_start": nullable,
                "measured_end": nullable,
                "timezone": string,
                "original_offset_minutes": {"type": "integer"},
                "designation": obj(
                    {
                        "action": {"enum": ["make_representative", "leave_unchanged"]},
                        "expected_etag": string,
                    },
                    ["action"],
                ),
                "note_operation": obj(
                    {
                        "text": {"type": "string", "maxLength": 16384},
                        "visibility": {"const": "private"},
                    },
                    ["text", "visibility"],
                ),
            },
            ["value", "unit", "clinical_date", "time_precision"],
        ),
        "Unavailable": obj(
            {
                "value": {"type": "null"},
                "absent_reason": string,
                "availability": {
                    "enum": ["awaiting_data", "awaiting_integration", "unavailable", "partial"]
                },
            },
            ["value", "absent_reason", "availability"],
        ),
    }
)
for path, item in schema["paths"].items():
    for method, operation in item.items():
        if method not in {"get", "post", "patch", "delete", "put"}:
            continue
        operation["responses"]["default"] = {
            "description": "Fail-closed structured error; endpoint implementation and release coverage are tracked separately.",
            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}},
        }
        if path.startswith("/api/v1/body/weights") and method in {"post", "patch"}:
            operation["requestBody"] = {
                "required": True,
                "content": {
                    "application/json": {"schema": {"$ref": "#/components/schemas/WeightInput"}}
                },
            }
            operation["responses"]["200"] = {
                "description": "Committed authorized revision",
                "content": {
                    "application/json": {"schema": {"$ref": "#/components/schemas/Record"}}
                },
            }
(root / "contracts/openapi.yaml").write_text(json.dumps(schema, indent=2) + "\n")
digest = hashlib.sha256((root / "contracts/openapi.yaml").read_bytes()).hexdigest()
(root / "contracts/openapi.sha256").write_text(digest + "\n")
(root / "frontend/generated/backend.ts").write_text(
    '''// Generated by scripts/build_backend_contracts.py; health values remain memory-only.
export type DecimalString = string;
export type ClinicalDate = string;
export interface DomainRecord<T = Record<string, unknown>> {
  id: string; revision_id: string; kind: string; version: number; etag: string;
  clinical_date: ClinicalDate | null; received_at: string; data: T;
}
export interface Page<T> { items: T[]; cursor: string | null }
export interface ApiError { error: {code: string; message: string; field_errors: {path: string; code: string; message: string}[]; request_id: string | null; retryable: boolean} }
export interface WeightInput {value: DecimalString; unit: 'kg' | 'lb'; clinical_date: ClinicalDate; time_precision: 'day' | 'minute' | 'second'; measured_start?: string | null; timezone?: string; original_offset_minutes?: number; designation?: {action: 'make_representative' | 'leave_unchanged'; expected_etag?: string}; note_operation?: {text: string; visibility: 'private'}}
export interface WeightValue {value: DecimalString; unit: 'kg' | 'lb'; canonical_value: DecimalString; canonical_unit: 'kg'; source_type: 'manual'; method_version: 'mass-v1'}
export const schemaSha256 = "'''
    + digest
    + '";\n'
)
