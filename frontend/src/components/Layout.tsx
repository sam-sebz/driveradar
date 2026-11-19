import { NavLink, Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

const link = ({ isActive }: { isActive: boolean }) =>
  `rounded-md px-3 py-2 text-sm font-medium ${
    isActive ? "bg-indigo-50 text-indigo-700" : "text-slate-600 hover:text-slate-900"
  }`;

export function Layout() {
  const { tokens, logout } = useAuth();
  const location = useLocation();
  if (!tokens) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  const isCoordinator = tokens.role === "coordinator";

  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <nav className="mx-auto flex max-w-6xl flex-wrap items-center gap-2 px-4 py-3">
          <span className="mr-4 text-lg font-bold text-indigo-700">DriveRadar</span>
          {isCoordinator ? (
            <NavLink to="/analytics" className={link}>
              Analytics
            </NavLink>
          ) : (
            <>
              <NavLink to="/" end className={link}>
                Dashboard
              </NavLink>
              <NavLink to="/upload" className={link}>
                Upload
              </NavLink>
              <NavLink to="/profile" className={link}>
                Profile
              </NavLink>
            </>
          )}
          <button type="button" onClick={logout} className="btn-secondary ml-auto">
            Log out
          </button>
        </nav>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}

export function ErrorBox({ error }: { error: unknown }) {
  if (!error) return null;
  const message = error instanceof Error ? error.message : "Something went wrong";
  return (
    <p role="alert" className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">
      {message}
    </p>
  );
}
