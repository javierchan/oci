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
  const { theme, setTheme, hydrated } = useTheme();
  const isActive = (value: ThemeOption["value"]): boolean => hydrated && theme === value;

  return (
    <div>
      <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-[var(--color-text-muted)]">
        Theme
      </p>
      <div className="grid grid-cols-3 gap-1 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-3)] p-1">
        {OPTIONS.map((option) => {
          const Icon = option.icon;
          const active = isActive(option.value);
          return (
            <button
              key={option.value}
              type="button"
              onClick={() => setTheme(option.value)}
              aria-pressed={active}
              disabled={!hydrated}
              className={[
                "inline-flex h-11 min-w-0 flex-col items-center justify-center gap-1 rounded-lg px-1 text-[10px] font-semibold leading-none transition-colors",
                active
                  ? "bg-[var(--color-accent)] text-white shadow-sm"
                  : "text-[var(--color-text-secondary)] hover:bg-[var(--color-surface)] hover:text-[var(--color-text-primary)]",
                !hydrated ? "cursor-wait opacity-70" : "",
              ].join(" ")}
            >
              <span className="flex h-4 w-4 items-center justify-center">
                <Icon className="h-4 w-4 shrink-0 stroke-2" />
              </span>
              <span className="max-w-full truncate leading-none">{option.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
