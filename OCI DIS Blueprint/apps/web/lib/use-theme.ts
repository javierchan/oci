"use client";

import { useEffect, useState } from "react";

const STORAGE_KEY = "oci-dis-theme";

export type Theme = "light" | "dark" | "system";

function isTheme(value: string | null): value is Theme {
  return value === "light" || value === "dark" || value === "system";
}

export function useTheme(): {
  theme: Theme;
  setTheme: (_theme: Theme) => void;
  hydrated: boolean;
} {
  const [theme, setTheme] = useState<Theme>("system");
  const [hydrated, setHydrated] = useState<boolean>(false);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const storedTheme = localStorage.getItem(STORAGE_KEY);
    if (isTheme(storedTheme)) {
      setTheme(storedTheme);
    }
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated || typeof window === "undefined") {
      return;
    }
    const root = document.documentElement;
    if (!root) {
      return;
    }
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const isDark = theme === "dark" || (theme === "system" && prefersDark);
    root.classList.toggle("dark", isDark);
    localStorage.setItem(STORAGE_KEY, theme);
  }, [hydrated, theme]);

  return { theme, setTheme, hydrated };
}
