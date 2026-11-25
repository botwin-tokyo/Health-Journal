"""Explicit operator-only synthetic unseal; never used by a startup service."""

import json
import ssl
from pathlib import Path

import httpx

operator = Path.home() / ".local/share/health03/operator"
context = ssl.create_default_context(cafile=str(operator / "synthetic-pki/server-ca.crt"))
with httpx.Client(
    base_url="https://127.0.0.1:8200", verify=context, trust_env=False, timeout=20
) as client:
    for number in (1, 2):
        status = client.get("/v1/sys/seal-status")
        status.raise_for_status()
        if not status.json()["sealed"]:
            break
        result = client.put(
            "/v1/sys/unseal",
            json={"key": (operator / f"synthetic-recovery/share-{number}").read_text()},
        )
        result.raise_for_status()
    status = client.get("/v1/sys/seal-status").json()
    assert not status["sealed"]
    print(
        json.dumps(
            {
                "sealed": status["sealed"],
                "shares": status["n"],
                "threshold": status["t"],
                "synthetic_only": True,
            }
        )
    )
