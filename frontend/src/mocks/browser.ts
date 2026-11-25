import { http, HttpResponse } from "msw";
import { setupWorker } from "msw/browser";
import fixture from "../../../contracts/fixtures/health03-v1/responses.json";
const responses = fixture as Record<string, unknown>;
const origin = "https://sample.example.invalid";
export async function startMocks() {
  const worker = setupWorker(
    http.all(origin + "/*", ({ request }) => {
      const path = new URL(request.url).pathname;
      const headers = {
        "X-Permission-Epoch": "synthetic-epoch",
        "Cache-Control": "no-store",
      };
      if (path === "/api/v1/auth/bootstrap")
        return HttpResponse.json({ csrf_token: "synthetic-only" }, { headers });
      if (path === "/internal/local-session")
        return HttpResponse.json(
          { status: "local_context_ready" },
          { headers },
        );
      if (path === "/api/v1/session") {
        const now = Date.now();
        return HttpResponse.json(
          {
            ...(responses[path] as object),
            server_time: new Date(now).toISOString(),
            idle_expires_at: new Date(now + 900000).toISOString(),
            absolute_expires_at: new Date(now + 43200000).toISOString(),
          },
          { headers },
        );
      }
      if (path === "/api/v1/session/activity")
        return HttpResponse.json(
          { idle_expires_at: new Date(Date.now() + 900000).toISOString() },
          { headers },
        );
      if (request.method !== "GET")
        return HttpResponse.json(
          { code: "read_only_sample_mode" },
          { status: 422, headers },
        );
      if (!(path in responses))
        return HttpResponse.json(
          { code: "sample_route_unavailable" },
          { status: 404, headers },
        );
      return HttpResponse.json(responses[path] as object, { headers });
    }),
  );
  await worker.start({
    quiet: true,
    serviceWorker: { url: "/mockServiceWorker.js" },
  });
}
