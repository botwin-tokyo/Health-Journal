#!/usr/bin/python3
"""Owner-authorized unattended Pi unlock using systemd-provided credentials."""

import json
import os
import ssl
import time
import urllib.error
import urllib.request
from pathlib import Path


def main():
    credentials = Path(os.environ["CREDENTIALS_DIRECTORY"])
    context = ssl.create_default_context(cafile=str(credentials / "unseal-ca"))
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}), urllib.request.HTTPSHandler(context=context)
    )

    def call(path, body=None):
        request = urllib.request.Request(
            "https://127.0.0.1:8200/v1/" + path,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Content-Type": "application/json"},
            method="PUT" if body is not None else "GET",
        )
        with opener.open(request, timeout=5) as response:
            return json.load(response)

    for attempt in range(30):
        try:
            status = call("sys/seal-status")
            if not status.get("initialized"):
                raise RuntimeError("Existing key service is not initialized")
            if not status["sealed"]:
                print("Local encryption service unlocked and ready", flush=True)
                return
            for number in (1, 2):
                status = call(
                    "sys/unseal", {"key": (credentials / f"unseal-{number}").read_text().strip()}
                )
                if not status["sealed"]:
                    print("Local encryption service unlocked and ready", flush=True)
                    return
        except (urllib.error.URLError, TimeoutError):
            pass
        time.sleep(1)
    raise RuntimeError("Local encryption service did not become ready")


if __name__ == "__main__":
    main()
