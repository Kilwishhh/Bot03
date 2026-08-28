import { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { api, User } from '../lib/api';

interface AuthContextValue {
  user: User | null;
  token: string | null;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, displayName?: string) => Promise<void>;
  logout: () => void;
  loading: boolean;
}

const AuthContext = createContext<AuthContextValue>({
  user: null, token: null,
  login: async () => {}, register: async () => {}, logout: () => {}, loading: false,
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(localStorage.getItem('mk_token'));
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (token) {
      api.me()
        .then(setUser)
        .catch(() => { localStorage.removeItem('mk_token'); setToken(null); })
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, [token]);

  const login = async (email: string, password: string) => {
    const { token: t, user: u } = await api.login(email, password);
    localStorage.setItem('mk_token', t);
    setToken(t);
    setUser(u);
  };

  const register = async (email: string, password: string, displayName?: string) => {
    await api.register(email, password, displayName);
    await login(email, password);
  };

  const logout = () => {
    api.logout().catch(() => {});
    localStorage.removeItem('mk_token');
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, token, login, register, logout, loading }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
