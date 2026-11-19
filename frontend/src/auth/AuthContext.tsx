import { useQueryClient } from "@tanstack/react-query";
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { getTokens, onTokensChange, setTokens } from "../api/client";
import type { Tokens } from "../api/schemas";

interface AuthState {
  tokens: Tokens | null;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [tokens, setState] = useState<Tokens | null>(getTokens());
  const qc = useQueryClient();
  useEffect(() => onTokensChange(setState), []);
  const logout = () => {
    setTokens(null);
    qc.clear();
  };
  return <AuthContext.Provider value={{ tokens, logout }}>{children}</AuthContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components -- hook belongs with its provider
export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
