import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { authApi } from "../api/auth";
import { configureApi } from "../api/client";
import type { User } from "../types/api";

type AuthContextValue = {
  user: User | null;
  token: string | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (name: string, email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const tokenRef = useRef<string | null>(null);

  const setAccessToken = useCallback((value: string | null) => {
    tokenRef.current = value;
    setToken(value);
  }, []);

  const refresh = useCallback(async () => {
    try {
      const data = await authApi.refresh();
      setAccessToken(data.access_token);
      const currentUser = await authApi.me();
      setUser(currentUser);
      return data.access_token;
    } catch {
      setAccessToken(null);
      setUser(null);
      return null;
    }
  }, [setAccessToken]);

  useEffect(() => {
    configureApi({
      getToken: () => tokenRef.current,
      onUnauthorized: refresh,
    });
  }, [refresh]);

  useEffect(() => {
    void refresh().finally(() => setLoading(false));
  }, [refresh]);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      token,
      loading,
      async login(email, password) {
        const data = await authApi.login(email, password);
        setAccessToken(data.access_token);
        const currentUser = await authApi.me();
        setUser(currentUser);
      },
      async register(name, email, password) {
        await authApi.register(name, email, password);
      },
      async logout() {
        try {
          await authApi.logout();
        } finally {
          setAccessToken(null);
          setUser(null);
        }
      },
    }),
    [loading, setAccessToken, token, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider.");
  return value;
}
