import json

import pytest
from config.production import configure
from django.core.exceptions import ImproperlyConfigured


def test_appliance_release_gate_is_bound_to_candidate(tmp_path, monkeypatch):
    gate = tmp_path / "release.json"
    (tmp_path / "desktop-proxy-secret").write_text("separate-desktop-credential")
    (tmp_path / "tunnel-origin-secret").write_text("separate-tunnel-credential")
    values = {"HEALTH03_UPLOAD_HOST": "phone.example.org"}
    for key, value in {
        "HEALTH03_PI_APPLIANCE": "1",
        "FRONTEND_ORIGIN": "https://localhost:5173",
        "API_ORIGIN": "https://localhost:8443",
        "API_HOSTNAME": "localhost",
        "PGUSER": "health03-app",
        "CREDENTIALS_DIRECTORY": str(tmp_path),
        "HEALTH03_RELEASE_GATE": str(gate),
        "HEALTH03_RELEASE_ID": "fixture",
        "HEALTH03_DEPLOYED_REVISION": "candidate",
    }.items():
        monkeypatch.setenv(key, value)
    for allowed, commit in [(False, "candidate"), (True, "other")]:
        gate.write_text(
            json.dumps({"release_id": "fixture", "production_allowed": allowed, "commit": commit})
        )
        with pytest.raises(ImproperlyConfigured, match="Release evidence"):
            configure(values.copy())
