import { createContext, useContext, useEffect, useState } from 'react';
import { api } from './api';

// 登录状态上下文：保存 token 与当前用户信息
const AuthCtx = createContext(null);
export const useAuth = () => useContext(AuthCtx);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const t = localStorage.getItem('token');
    if (!t) return setLoading(false);
    api.get('/api/auth/me').then(setUser).catch(() => localStorage.removeItem('token')).finally(() => setLoading(false));
  }, []);

  const login = async (username, password) => {
    const { access_token } = await api.login(username, password);
    localStorage.setItem('token', access_token);
    const me = await api.get('/api/auth/me');
    setUser(me);
  };
  const logout = () => {
    localStorage.removeItem('token');
    setUser(null);
    window.location.href = '/login';
  };
  return <AuthCtx.Provider value={{ user, login, logout, loading }}>{children}</AuthCtx.Provider>;
}
