"""Bounded untrusted input and restore evidence regression tests."""

import hashlib
import json

import pytest
from operations.restore import verify_ledger
from parser_service.operations import csv_cell, parse_csv


@pytest.mark.parametrize("value", ["=SUM(A1:A2)", "+cmd", "-cmd", "@cmd", "\tcmd", "\rcmd"])
def test_csv_formula_text_is_neutralized(value):
    assert csv_cell(value).startswith("'")


def test_numeric_negative_is_preserved():
    assert csv_cell("-12.5", numeric=True) == "-12.5"
    with pytest.raises(ValueError):
        csv_cell("NaN", numeric=True)


def test_csv_result_limit():
    with pytest.raises(ValueError, match="csv_too_large"):
        parse_csv(b"a,b\n" * 100001)


def test_restore_ledger_requires_independent_current_head(tmp_path, monkeypatch):
    event = {"action": "record_deleted", "owner_id": "synthetic", "target_id": "synthetic"}
    previous = "0" * 64
    digest = hashlib.sha256(
        (previous + json.dumps(event, sort_keys=True, separators=(",", ":"))).encode()
    ).hexdigest()
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text(
        json.dumps({"sequence": 1, "previous_hash": previous, "hash": digest, "event": event})
        + "\n"
    )
    head = tmp_path / "head.json"
    head.write_text(json.dumps({"sequence": 1, "hash": digest}))
    monkeypatch.setenv("RESTORE_LEDGER_HEAD", str(head))
    assert verify_ledger(ledger, 1, digest) == [event]
    head.write_text(json.dumps({"sequence": 2, "hash": "a" * 64}))
    with pytest.raises(ValueError, match="head"):
        verify_ledger(ledger, 1, digest)
    with pytest.raises(ValueError, match="incomplete"):
        verify_ledger(ledger, 2, digest)


def test_report_fixed_template_does_not_fetch_user_urls():
    from parser_service.operations import render_report

    payload = json.dumps(
        {
            "template": "appointment-v1",
            "sections": [
                {"heading": "<script>bad()</script>", "text": '<img src="file:///etc/passwd">'}
            ],
        }
    ).encode()
    assert render_report(payload).startswith(b"%PDF-")
    with pytest.raises(ValueError, match="invalid_report_snapshot"):
        render_report(b'{"template":"arbitrary", "sections":[]}')


def test_owner_no_backup_does_not_touch_external_configuration(settings, monkeypatch):
    from operations import backup, ledger

    settings.HEALTH03_BACKUPS_ENABLED = False
    monkeypatch.setattr(
        backup, "config", lambda: (_ for _ in ()).throw(AssertionError("must not configure backup"))
    )
    assert backup.perform() == {"state": "disabled_by_owner", "backup_created": False}
    assert ledger.publish()["state"] == "disabled_by_owner"
