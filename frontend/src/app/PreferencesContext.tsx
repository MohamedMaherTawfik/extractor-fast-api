import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import type { Language } from "../i18n/translations";

type Theme = "light" | "dark" | "system";
type Preferences = { language: Language; theme: Theme; sidebarCollapsed: boolean; setLanguage: (v: Language) => void; setTheme: (v: Theme) => void; setSidebarCollapsed: (v: boolean) => void };
const Context = createContext<Preferences | null>(null);

export function PreferencesProvider({ children }: { children: ReactNode }) {
  const [language, setLanguage] = useState<Language>(() => localStorage.getItem("emy.language") === "en" ? "en" : "ar");
  const [theme, setTheme] = useState<Theme>(() => (localStorage.getItem("emy.theme") as Theme) || "system");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => localStorage.getItem("emy.sidebar") === "collapsed");
  useEffect(() => { localStorage.setItem("emy.language", language); document.documentElement.lang = language; document.documentElement.dir = language === "ar" ? "rtl" : "ltr"; }, [language]);
  useEffect(() => {
    localStorage.setItem("emy.theme", theme);
    const dark = theme === "dark" || (theme === "system" && matchMedia("(prefers-color-scheme: dark)").matches);
    document.documentElement.dataset.theme = dark ? "dark" : "light";
  }, [theme]);
  useEffect(() => localStorage.setItem("emy.sidebar", sidebarCollapsed ? "collapsed" : "expanded"), [sidebarCollapsed]);
  const value = useMemo(() => ({ language, theme, sidebarCollapsed, setLanguage, setTheme, setSidebarCollapsed }), [language, theme, sidebarCollapsed]);
  return <Context.Provider value={value}>{children}</Context.Provider>;
}

export function usePreferences() { const value = useContext(Context); if (!value) throw new Error("PreferencesProvider is missing"); return value; }
