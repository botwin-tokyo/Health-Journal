# Local desktop access

The optional desktop profile supports automatic local entry. The dashboard at `https://localhost:5173` opens directly against the Pi API at `https://localhost:8443`.

`HEALTH03_LOCAL_DESKTOP=1` enables a CSRF-protected local session entry on the development backend only. It requires the exact localhost frontend origin, exact API Host and a loopback peer. It creates/reuses only the dedicated local desktop owner, never silently assumes a different existing owner. The ordinary per-record authorization, HttpOnly secure cookies, permission epochs, encryption and deletion policies still run. Local desktop authority satisfies management step-up; it is not presented as a verified password event.

Production startup rejects the development flag. The [production Pi profile](../operations/pi-production.md) supports automatic entry through its authenticated loopback proxy. Public builds use the password screens and must omit `VITE_LOCAL_DESKTOP=1`.
