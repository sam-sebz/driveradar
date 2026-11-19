import { useState, type FormEvent } from "react";
import { Link, Navigate } from "react-router-dom";
import { useLogin, useSignup } from "../api/hooks";
import { useAuth } from "../auth/AuthContext";
import { ErrorBox } from "../components/Layout";

export function AuthPage({ mode }: { mode: "login" | "signup" }) {
  const { tokens } = useAuth();
  const login = useLogin();
  const signup = useSignup();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const action = mode === "login" ? login : signup;

  if (tokens) return <Navigate to={tokens.role === "coordinator" ? "/analytics" : "/"} replace />;

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (mode === "login") login.mutate({ email, password });
    else signup.mutate({ email, password, name: name || undefined });
  };

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <form onSubmit={submit} className="card w-full max-w-sm space-y-4">
        <div>
          <h1 className="text-2xl font-bold text-indigo-700">DriveRadar</h1>
          <p className="text-sm text-slate-600">
            {mode === "login" ? "Log in to see your drives." : "Create a student account."}
          </p>
        </div>
        {mode === "signup" && (
          <div>
            <label className="label" htmlFor="name">
              Name
            </label>
            <input id="name" className="input" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
        )}
        <div>
          <label className="label" htmlFor="email">
            Email
          </label>
          <input
            id="email"
            type="email"
            required
            autoComplete="email"
            className="input"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
        <div>
          <label className="label" htmlFor="password">
            Password
          </label>
          <input
            id="password"
            type="password"
            required
            minLength={mode === "signup" ? 8 : 1}
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            className="input"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          {mode === "signup" && (
            <p className="mt-1 text-xs text-slate-500">At least 8 characters, a letter and a digit.</p>
          )}
        </div>
        <ErrorBox error={action.error} />
        <button type="submit" className="btn w-full" disabled={action.isPending}>
          {mode === "login" ? "Log in" : "Sign up"}
        </button>
        <p className="text-center text-sm text-slate-600">
          {mode === "login" ? (
            <>
              New here? <Link className="text-indigo-700 underline" to="/signup">Create an account</Link>
            </>
          ) : (
            <>
              Have an account? <Link className="text-indigo-700 underline" to="/login">Log in</Link>
            </>
          )}
        </p>
        {mode === "login" && (
          <p className="rounded-md bg-slate-100 p-2 text-xs text-slate-600">
            Demo: demo@driveradar.dev / Demo@1234 (student), coordinator@driveradar.dev / Demo@1234
          </p>
        )}
      </form>
    </div>
  );
}
