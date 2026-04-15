"use client";

import { useEffect, useState } from "react";

const STORAGE_KEY = "oci-dis-theme";

export type Theme = "light" | "dark" | "system";

export function useTheme(): {
  theme: Theme;
  setTheme: (_theme: Theme) => void;
} {
  const [theme, setTheme] = useState<Theme>(() => {
    if (typeof window === "undefined") {
      return "system";
    }
    return (localStorage.getItem(STORAGE_KEY) as Theme | null) ?? "system";
  });

  useEffect(() => {
    const root = document.documentElement;
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const isDark = theme === "dark" || (theme === "system" && prefersDark);
    root.classList.toggle("dark", isDark);
    localStorage.setItem(STORAGE_KEY, theme);
  }, [theme]);

  return { theme, setTheme };
}
