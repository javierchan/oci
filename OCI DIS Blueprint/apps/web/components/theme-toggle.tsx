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
      <p className="mb-3 text-xs uppercase tracking-[0.25em] text-[var(--color-text-muted)]">Theme</p>
      <div className="grid grid-cols-3 gap-2 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-2)] p-1.5">
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
                "inline-flex min-h-14 flex-col items-center justify-center gap-1 rounded-xl px-2 py-2 text-xs font-semibold leading-none transition",
                active
                  ? "bg-[var(--color-accent)] text-white"
                  : "text-[var(--color-text-secondary)] hover:bg-[var(--color-surface)] hover:text-[var(--color-text-primary)]",
                !hydrated ? "cursor-wait opacity-70" : "",
              ].join(" ")}
            >
              <span className="flex h-7 w-7 items-center justify-center">
                <Icon className="h-[1.4rem] w-[1.4rem] shrink-0 stroke-[2.25]" />
              </span>
              <span className="leading-none">{option.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
