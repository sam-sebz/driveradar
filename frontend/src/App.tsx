import { QueryClientProvider } from "@tanstack/react-query";
import { Suspense, lazy, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import { Layout } from "./components/Layout";
import { AuthPage } from "./pages/AuthPage";
import { DashboardPage } from "./pages/DashboardPage";
import { DriveDetailPage } from "./pages/DriveDetailPage";
import { ProfilePage } from "./pages/ProfilePage";
import { UploadPage } from "./pages/UploadPage";
import { makeQueryClient } from "./lib/queryClient";

// Recharts is large; only coordinators download it.
const AnalyticsPage = lazy(() =>
  import("./pages/AnalyticsPage").then((m) => ({ default: m.AnalyticsPage })),
);

function StudentOnly({ children }: { children: JSX.Element }) {
  const { tokens } = useAuth();
  return tokens?.role === "coordinator" ? <Navigate to="/analytics" replace /> : children;
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<AuthPage mode="login" />} />
      <Route path="/signup" element={<AuthPage mode="signup" />} />
      <Route element={<Layout />}>
        <Route path="/" element={<StudentOnly><DashboardPage /></StudentOnly>} />
        <Route path="/upload" element={<StudentOnly><UploadPage /></StudentOnly>} />
        <Route path="/profile" element={<StudentOnly><ProfilePage /></StudentOnly>} />
        <Route path="/drives/:id" element={<StudentOnly><DriveDetailPage /></StudentOnly>} />
        <Route
          path="/analytics"
          element={
            <Suspense fallback={<p className="text-sm text-slate-500">Loading...</p>}>
              <AnalyticsPage />
            </Suspense>
          }
        />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  const [client] = useState(makeQueryClient);
  return (
    <QueryClientProvider client={client}>
      <AuthProvider>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}
