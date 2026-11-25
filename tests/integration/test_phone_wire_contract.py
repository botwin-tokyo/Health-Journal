import json
from pathlib import Path

import pytest
from ingest.contract import schema
from ingest.mapping import normalize
from jsonschema import Draft202012Validator
from records.validation import DomainError

FIXTURES = json.loads((Path(__file__).parents[2] / "contracts/phone/fixtures.json").read_text())


def test_schema_is_valid():
    Draft202012Validator.check_schema(schema())


@pytest.mark.parametrize("case", FIXTURES, ids=lambda case: case["name"])
def test_documented_wire_fixture(case):
    expected = case["expected"]
    if expected["outcome"] == "rejected":
        with pytest.raises(DomainError) as error:
            normalize(case["item"])
        assert error.value.code == expected["reason"]
    else:
        kind, _, _, data = normalize(case["item"])
        assert kind == expected["record_kind"]
        assert data["record_status"] == expected["disposition"]
        if case["name"] == "sleep_stages":
            assert data["clinical_date"] == "2020-01-02"
        if case["name"] == "mir_trials":
            assert len(data["trials"]) == 2 and data["trials"][1]["clinical_eligible"] is False
            assert data["values"]["fev1"] == "2.9"
