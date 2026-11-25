import { afterEach, expect, it, vi } from "vitest";
const session = {
  account_id: "synthetic",
  role: "owner",
  context: { owner_id: "synthetic", grant_id: null, view_mode: "owner" },
  permission_epoch: "one",
  csrf_token: "sample",
  idle_expires_at: new Date(Date.now() + 900000).toISOString(),
  absolute_expires_at: new Date(Date.now() + 43200000).toISOString(),
  server_time: new Date().toISOString(),
  capabilities: ["read"],
};
afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  vi.resetModules();
});
it("rejects an in-flight response after protected context is cleared", async () => {
  vi.stubEnv("VITE_LOCAL_DESKTOP", "0");
  let finish!: (r: Response) => void;
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValueOnce(Response.json(session))
      .mockImplementationOnce(
        () =>
          new Promise<Response>((resolve) => {
            finish = resolve;
          }),
      ),
  );
  const transport = await import("./transport");
  await transport.refreshSession();
  const pending = transport.api("/api/v1/overview");
  transport.clearProtected();
  finish(
    Response.json(
      { private_text: "must not be accepted" },
      { headers: { "X-Permission-Epoch": "one" } },
    ),
  );
  await expect(pending).rejects.toMatchObject({
    code: "permission_context_changed",
  });
  expect(transport.authStore.snapshot().session).toBeNull();
});
it("clears cached data and cleanup tasks on a changed session epoch", async () => {
  vi.stubEnv("VITE_LOCAL_DESKTOP", "0");
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValueOnce(Response.json(session))
      .mockResolvedValueOnce(
        Response.json({ ...session, permission_epoch: "two" }),
      ),
  );
  const transport = await import("./transport");
  await transport.refreshSession();
  transport.queryClient.setQueryData(["private"], { text: "old context" });
  const clear = vi.fn();
  transport.registerCleanup(clear);
  await transport.refreshSession();
  expect(clear).toHaveBeenCalledOnce();
  expect(transport.queryClient.getQueryData(["private"])).toBeUndefined();
  expect(transport.authStore.snapshot().session?.permission_epoch).toBe("two");
});

it("accepts a terminal deletion receipt without restarting authentication", async () => {
  vi.stubEnv("VITE_LOCAL_DESKTOP", "0");
  const fetcher = vi
    .fn()
    .mockResolvedValueOnce(Response.json(session))
    .mockResolvedValueOnce(
      Response.json({
        accepted_at: new Date().toISOString(),
        purge_by: new Date(Date.now() + 86400000).toISOString(),
        durability: "local_only",
      }),
    );
  vi.stubGlobal("fetch", fetcher);
  const transport = await import("./transport");
  await transport.refreshSession();
  await transport.api("/api/v1/account/deletion-requests", {
    method: "POST",
    body: { scope: "account", confirm: true },
  });
  expect(transport.authStore.snapshot().phase).toBe("closed");
  transport.clearProtected("checking");
  await transport.refreshSession();
  expect(transport.authStore.snapshot().phase).toBe("closed");
  expect(fetcher).toHaveBeenCalledTimes(2);
});
