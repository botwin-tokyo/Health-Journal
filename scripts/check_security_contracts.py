"""S00 structural checks; not a claim that runtime controls are implemented."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(name):
    return json.loads((ROOT / name).read_text())


def main():
    operations = read("contracts/security/operations.json")["operations"]
    schema = read("contracts/openapi.yaml")
    mapped = {(o["method"], o["path"]) for o in operations}
    actual = {
        (m.upper(), p)
        for p, item in schema["paths"].items()
        for m in item
        if m in {"get", "post", "put", "patch", "delete"}
    }
    assert mapped == actual, "Policy/OpenAPI surface drift"
    matrix = (ROOT / "docs/security/permission-matrix.md").read_text()
    expected = set(re.findall(r"^\| `(GET|POST|PUT|PATCH|DELETE) ([^ `]+)`", matrix, re.M))
    assert mapped == expected, "Published permission matrix differs from operation contracts"
    for o in operations:
        assert o["roles"] and o["policy"] and isinstance(o["implemented"], bool)
        if "/ingestion/" in o["path"]:
            assert o["roles"] == ["uploader"] and not o["csrf"]
        elif o["method"] not in {"GET", "HEAD", "OPTIONS"}:
            assert o["csrf"]
    inventory = read("contracts/security/data-inventory.json")
    names = {e["entity"] for e in inventory["entities"]}
    assert len(names) == len(inventory["entities"])
    allowed = {
        "routing_metadata",
        "authentication_restricted",
        "envelope_encrypted",
        "envelope_metadata",
        "ciphertext",
    }
    for e in inventory["entities"]:
        assert e["owner"] and e["fields"]
        assert set(e["fields"].values()) <= allowed
    for entity in [
        "RecordRevision",
        "BlobObject",
        "JournalRevision",
        "MedicationEventRevision",
        "QuestionRevision",
        "LabResult",
        "ReportSnapshot",
        "ProfileRevision",
    ]:
        assert (
            "envelope_encrypted"
            in next(e for e in inventory["entities"] if e["entity"] == entity)["fields"].values()
        )
    fixture = read("tests/fixtures/synthetic/security-v1.json")
    assert (
        fixture["synthetic_only"] and len(fixture["grants"]) == 2 and len(fixture["devices"]) == 2
    )
    assert all(a["email"].endswith("@example.invalid") for a in fixture["accounts"])
    ids = (
        {r["id"] for r in fixture["records"]}
        | {r["id"] for r in fixture["documents"]}
        | {r["id"] for r in fixture["baselines"]}
    )
    assert all(c["target"] in ids for c in fixture["expected_cases"])
    assert {c.get("allowed") for c in fixture["expected_cases"]} == {True, False}
    print(
        f"S00 coverage PASS: {len(mapped)} operations, {len(names)} classified entities, {len(fixture['expected_cases'])} fictional policy cases. Runtime gates remain pending."
    )


if __name__ == "__main__":
    main()
