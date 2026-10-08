import { createContext, useContext, useEffect, useState } from 'react';
import { THEMES, DEFAULT_THEME, getTheme } from './themes';

// 主题：CSS 变量驱动，tailwind 语义色全部映射到 --th-* 变量，
// 切换主题时类名不用改，颜色自动跟随。
const ThemeContext = createContext({ themeId: DEFAULT_THEME, theme: THEMES[DEFAULT_THEME], setTheme: () => {} });

const VAR_KEYS = ['bg', 'card', 'pri', 'prid', 'acc', 'txt', 'mut', 'line'];
const STORAGE_KEY = 'yoga-theme';

export function ThemeProvider({ children }) {
  const [themeId, setThemeId] = useState(() => {
    try { return localStorage.getItem(STORAGE_KEY) || DEFAULT_THEME; } catch { return DEFAULT_THEME; }
  });

  useEffect(() => {
    const t = getTheme(themeId);
    const root = document.documentElement;
    root.dataset.theme = themeId;
    VAR_KEYS.forEach((k) => root.style.setProperty(`--th-${k}`, t[k]));
  }, [themeId]);

  const setTheme = (id) => {
    if (!THEMES[id]) return;
    try { localStorage.setItem(STORAGE_KEY, id); } catch {}
    setThemeId(id);
  };

  return (
    <ThemeContext.Provider value={{ themeId, theme: getTheme(themeId), setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export const useTheme = () => useContext(ThemeContext);
