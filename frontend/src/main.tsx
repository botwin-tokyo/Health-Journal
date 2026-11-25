import { createRoot } from "react-dom/client";
import { RouterProvider } from "react-router/dom";
import { QueryClientProvider } from "@tanstack/react-query";
import { queryClient } from "./api/transport";
import { router } from "./app/router";
import "./styles/tokens.css";
if (__SAMPLE_MODE__) await import("./mocks/browser").then(m=>m.startMocks());
createRoot(document.getElementById("root")!).render(
  <QueryClientProvider client={queryClient}>
    <RouterProvider router={router} />
  </QueryClientProvider>,
);
