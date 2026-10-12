import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import {
  clearSession,
  completeMfaLogin,
  getStoredUser,
  getToken,
  login as apiLogin,
  storeUser,
  type User,
} from "./api";

type AuthState = {
  user: User | null;
  token: string | null;
  login: (
    email: string,
    password: string,
  ) => Promise<{ user: User; mfaRequired?: false } | { mfaRequired: true; mfaToken: string; user: User }>;
  finishMfa: (mfaToken: string, code: string) => Promise<User>;
  logout: () => void;
  setUser: (user: User) => void;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUserState] = useState<User | null>(() => getStoredUser());
  const [token, setToken] = useState<string | null>(() => getToken());

  const value = useMemo<AuthState>(
    () => ({
      user,
      token,
      async login(email, password) {
        const data = await apiLogin(email, password);
        if ("mfaRequired" in data && data.mfaRequired) {
          return { mfaRequired: true, mfaToken: data.mfaToken, user: data.user };
        }
        setUserState(data.user);
        setToken(data.access_token);
        return { user: data.user };
      },
      async finishMfa(mfaToken, code) {
        const data = await completeMfaLogin(mfaToken, code);
        setUserState(data.user);
        setToken(data.access_token);
        return data.user;
      },
      logout() {
        clearSession();
        setUserState(null);
        setToken(null);
      },
      setUser(next) {
        storeUser(next);
        setUserState(next);
      },
    }),
    [user, token],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth fuera de AuthProvider");
  return ctx;
}
