# Local dashboard

Open **https://localhost:5173** on this Pi. The local dashboard opens directly: no email, password or enrollment screen. `/login` also returns directly to Overview. API requests use the loopback HTTPS bridge at `https://localhost:8443`; the actual Django backend runs at `127.0.0.1:8000`.

The local entry endpoint requires development mode, the exact configured localhost origins, loopback peer address and CSRF. It refuses a different pre-existing owner. Public deployments must disable `HEALTH03_LOCAL_DESKTOP` and `VITE_LOCAL_DESKTOP`; the Pi appliance uses a separate authenticated loopback proxy.

Use a dedicated database for your own records. Synthetic acceptance uses a separate PostgreSQL database, `health03_frontend_acceptance`, and separate encrypted blob directory.

## Services and build

For the fictional preview, copy `.env.example` to `.env` in the repository root. In `frontend/`, run `pnpm install --frozen-lockfile` with Node 24 and pnpm 10, then `pnpm dev`. Open the printed loopback URL. Set optional display settings in the root `.env`. The preview uses local sample data. Use `pnpm dev:api` to connect to a configured backend.

```sh
systemctl --user status health03-dashboard health03-api-proxy
systemctl status health03-local-app health03-local-worker
scripts/frontend check:api
scripts/frontend typecheck
scripts/frontend lint
scripts/frontend test
scripts/frontend build
systemctl --user restart health03-dashboard
```

`health03-dashboard` serves the static production bundle over local HTTPS with a restrictive CSP and deep-link fallback. `health03-api-proxy` terminates local HTTPS and forwards to the loopback Pi API. User services start with the desktop session. Backend services start with the machine. Install the local CA in system trust and the desktop NSS database; its private material stays in ignored `.local/frontend-tls/`.

For interactive editing, stop `health03-dashboard` before using `scripts/frontend dev:api` on port 5173. Restart the service after building. `scripts/frontend dev:mock --port 5175` uses an explicit, read-only synthetic MSW preview with a sample banner; mock code, responses and its worker are excluded from the production build. Do not use the synthetic API port for the owner dashboard.

## Acceptance fixture

The checked-in `contracts/fixtures/health03-v1/responses.json` is captured from fictional encrypted backend records. It contains no owner data, passwords, cookies or usable CSRF token. `frontend/scripts/capture-fixture.mjs` is fixed to the isolated test API and verifies the synthetic-session marker before writing fixtures.

To recreate that environment, create the dedicated database, run migrations with `PGDATABASE=health03_frontend_acceptance`, then run `prepare_frontend_acceptance` in development with access to the local KMS and an isolated blob directory. The command refuses every other database and any non-fictional identity. It writes the random test password to the ignored, mode-0600 `.local/frontend-test-password` file. Run the test API at 8001 with frontend/API origins `https://localhost:5174` and `https://localhost:8444`; run the TLS proxy with `HEALTH03_PROXY_PORT=8444 HEALTH03_UPSTREAM_PORT=8001`, and Vite with `VITE_LOCAL_DESKTOP=0 VITE_API_BASE_URL=https://localhost:8444/api/v1 scripts/frontend dev:api --port 5174`.

PDF acceptance additionally needs an isolated worker using the existing protected parser service. Its worker database and blob root must match the synthetic API, never the owner database. Tests use a fictional PDF at `/tmp/health03-synthetic-lab.pdf`. `scripts/frontend test:e2e` covers Chromium, Firefox and WebKit; `test:a11y` selects the route accessibility checks. The synthetic setup uses a password solely to exercise future public authentication; the owner's localhost dashboard does not.

The optional final teardown check runs with `HEALTH03_DELETE_FIXTURE=1 scripts/frontend test:e2e --project chromium --grep "accepted deletion"`. It closes only the isolated fixture owner; recreate that disposable database for a later full run. The preparation command refuses a previously closed fixture.

Snap browsers have separate certificate stores. Run `scripts/trust_local_dashboard.sh` after creating a browser profile, then restart that browser. It imports only this Pi’s local CA into existing Chromium/Firefox NSS databases; it does not bypass certificate validation.
