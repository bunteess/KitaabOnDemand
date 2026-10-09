import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { api, setSessionExpiredHandler, unwrap, type Schemas } from "../api/client";
import { tokens } from "../api/tokens";

type Me = Schemas["MeOut"];

interface AuthState {
  user: Me | null;
  /** True until the saved session has been checked. */
  restoring: boolean;
  expired: boolean;
  login(email: string, password: string, totpCode?: string): Promise<Me>;
  logout(): Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Me | null>(null);
  const [restoring, setRestoring] = useState(() => tokens.refresh() !== null);
  const [expired, setExpired] = useState(false);

  useEffect(() => {
    setSessionExpiredHandler(() => {
      tokens.clear();
      setUser(null);
      setExpired(true);
    });
    if (!tokens.refresh()) return;
    // A reload keeps only the refresh token; /me triggers a refresh.
    unwrap(api.GET("/api/v1/me"))
      .then(setUser)
      .catch(() => tokens.clear())
      .finally(() => setRestoring(false));
  }, []);

  const login = useCallback(async (email: string, password: string, totpCode?: string) => {
    const pair = await unwrap(
      api.POST("/api/v1/auth/staff/login", {
        body: { email, password, totp_code: totpCode || null },
      }),
    );
    tokens.save(pair.access_token, pair.refresh_token);
    setExpired(false);
    setUser(pair.user);
    return pair.user;
  }, []);

  const logout = useCallback(async () => {
    const refresh = tokens.refresh();
    tokens.clear();
    setUser(null);
    if (refresh)
      await api
        .POST("/api/v1/auth/logout", { body: { refresh_token: refresh } })
        .catch(() => undefined);
  }, []);

  const value = useMemo(
    () => ({ user, restoring, expired, login, logout }),
    [user, restoring, expired, login, logout],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
