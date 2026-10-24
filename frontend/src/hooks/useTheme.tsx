import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import type { Theme } from "@/types";

const Ctx = createContext<{ theme: Theme; resolved: "dark" | "light"; setTheme: (t: Theme) => void } | null>(null);

function resolve(t: Theme): "dark" | "light" {
  if (t === "system") return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  return t;
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(() => (localStorage.getItem("lm-theme") as Theme) || "dark");
  const [resolved, setResolved] = useState<"dark" | "light">(() => resolve(theme));

  useEffect(() => {
    const r = resolve(theme);
    setResolved(r);
    document.documentElement.classList.toggle("dark", r === "dark");
    if (theme !== "system") return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const fn = () => {
      const x = resolve("system");
      setResolved(x);
      document.documentElement.classList.toggle("dark", x === "dark");
    };
    mq.addEventListener("change", fn);
    return () => mq.removeEventListener("change", fn);
  }, [theme]);

  const setTheme = useCallback((t: Theme) => {
    localStorage.setItem("lm-theme", t);
    setThemeState(t);
  }, []);

  return <Ctx.Provider value={{ theme, resolved, setTheme }}>{children}</Ctx.Provider>;
}

export function useTheme() {
  const c = useContext(Ctx);
  if (!c) throw new Error("useTheme must be used inside ThemeProvider");
  return c;
}
