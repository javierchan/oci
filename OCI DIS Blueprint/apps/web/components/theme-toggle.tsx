"use client";

/* Sidebar theme toggle with light/system/dark modes persisted in local storage. */

import { Monitor, Moon, Sun } from "lucide-react";

import { useTheme } from "@/lib/use-theme";

type ThemeOption = {
  label: string;
  value: "light" | "system" | "dark";
  icon: typeof Sun;
};

const OPTIONS: ThemeOption[] = [
  { label: "Light", value: "light", icon: Sun },
  { label: "System", value: "system", icon: Monitor },
  { label: "Dark", value: "dark", icon: Moon },
];

export function ThemeToggle(): JSX.Element {
  const { theme, setTheme } = useTheme();

  return (
    <div>
      <p className="mb-3 text-xs uppercase tracking-[0.25em] text-[var(--color-text-muted)]">Theme</p>
      <div className="grid grid-cols-3 gap-2 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-2)] p-1">
        {OPTIONS.map((option) => {
          const Icon = option.icon;
          const active = theme === option.value;
          return (
            <button
              key={option.value}
              type="button"
              onClick={() => setTheme(option.value)}
              className={[
                "inline-flex items-center justify-center gap-2 rounded-xl px-3 py-2 text-xs font-semibold transition",
                active
                  ? "bg-[var(--color-accent)] text-white"
                  : "text-[var(--color-text-secondary)] hover:bg-[var(--color-surface)] hover:text-[var(--color-text-primary)]",
              ].join(" ")}
            >
              <Icon className="h-4 w-4" />
              <span>{option.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
