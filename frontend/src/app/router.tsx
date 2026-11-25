import { createBrowserRouter, Navigate } from "react-router";
import Shell from "./Shell";
import Auth, { Boundary } from "./Auth";
import { lazy, Suspense } from "react";
const Overview = lazy(() => import("../features/Overview"));
const Settings = lazy(() => import("../features/Settings"));
const Review = lazy(() => import("../features/Review"));
const Labs = lazy(() => import("../features/Labs"));
const BloodPressure = lazy(() => import("../features/BloodPressure"));
const Sleep = lazy(() => import("../features/Sleep"));
const Breathing = lazy(() => import("../features/Breathing"));
const Body = lazy(() => import("../features/Body"));
const Journal = lazy(() => import("../features/Journal"));
import { Card } from "../components/ui";
const routeError = (
  <main className="auth">
    <Card title="This view could not be loaded">
      <p>
        Please reload the journal. If the problem continues, check the Pi
        backend.
      </p>
      <a href="/">Reload journal</a>
    </Card>
  </main>
);
export const router = createBrowserRouter([
  {
    errorElement: routeError,
    children: [
      {
        element: <Boundary />,
        children: [
          {
            element: <Shell />,
            children: [
              { index: true, element: <Navigate to="/overview" replace /> },
              ...[
                "overview",
                "body",
                "breathing",
                "sleep-activity",
                "blood-pressure",
                "journal",
                "labs",
                "doctor-review",
                "settings",
              ].map((path) => ({
                path,
                element: (
                  <Suspense fallback={<p>Loading page…</p>}>
                    {path === "overview" ? (
                      <Overview />
                    ) : path === "settings" ? (
                      <Settings />
                    ) : path === "doctor-review" ? (
                      <Review />
                    ) : path === "labs" ? (
                      <Labs />
                    ) : path === "blood-pressure" ? (
                      <BloodPressure />
                    ) : path === "sleep-activity" ? (
                      <Sleep />
                    ) : path === "breathing" ? (
                      <Breathing />
                    ) : path === "body" ? (
                      <Body />
                    ) : path === "journal" ? (
                      <Journal />
                    ) : null}
                  </Suspense>
                ),
              })),
            ],
          },
        ],
      },
      ...[
        "login",
        "enroll",
        "reset-password",
        "verify-email",
        "reauthenticate",
        "change-password",
      ].map((path) => ({ path, element: <Auth /> })),
      {
        path: "account-deleted",
        element: (
          <main className="auth">
            <Card title="Journal closed">
              <p>Your deletion request has been accepted.</p>
            </Card>
          </main>
        ),
      },
      {
        path: "*",
        element: (
          <main className="auth">
            <Card title="Page unavailable">
              <a href="/">Return to your journal</a>
            </Card>
          </main>
        ),
      },
    ],
  },
]);
