"use client";

/* Autocomplete input backed by known source and destination systems in the catalog. */

import { useEffect, useMemo, useState } from "react";

import { api } from "@/lib/api";

type SystemAutocompleteProps = {
  projectId: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  description?: string;
};

export function SystemAutocomplete({
  projectId,
  label,
  value,
  onChange,
  placeholder,
  description,
}: SystemAutocompleteProps): JSX.Element {
  const [systems, setSystems] = useState<string[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [focused, setFocused] = useState<boolean>(false);
  const query = value.trim();

  useEffect(() => {
    let cancelled = false;

    async function loadSystems(): Promise<void> {
      try {
        const response = await api.getSystems(projectId);
        if (!cancelled) {
          setSystems(response);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void loadSystems();

    return () => {
      cancelled = true;
    };
  }, [projectId]);

  const suggestions = useMemo(
    () =>
      systems
        .filter((system) => system.toLowerCase().includes(query.toLowerCase()))
        .slice(0, 8),
    [query, systems],
  );

  return (
    <label className="block">
      <span className="mb-2 block text-xs uppercase tracking-[0.25em] text-slate-500">{label}</span>
      <div className="relative">
        <input
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onFocus={() => setFocused(true)}
          onBlur={() => {
            window.setTimeout(() => setFocused(false), 150);
          }}
          placeholder={placeholder}
          className="app-input"
        />
        {focused && suggestions.length > 0 ? (
          <div className="absolute z-10 mt-2 w-full overflow-hidden rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] shadow-xl">
            {suggestions.map((system) => (
              <button
                key={system}
                type="button"
                onMouseDown={() => onChange(system)}
                className="block w-full px-4 py-3 text-left text-sm text-[var(--color-text-secondary)] transition hover:bg-[var(--color-surface-2)] hover:text-[var(--color-text-primary)]"
              >
                {system}
              </button>
            ))}
          </div>
        ) : null}
      </div>
      {focused && query.length >= 2 && loading ? (
        <div className="mt-1 rounded-md border border-[var(--color-border)] bg-[var(--color-surface-2)] px-3 py-2 text-sm italic text-[var(--color-text-muted)]">
          Searching…
        </div>
      ) : null}
      {focused && query.length >= 2 && !loading && suggestions.length === 0 ? (
        <div className="mt-1 rounded-md border border-[var(--color-border)] bg-[var(--color-surface-2)] px-3 py-2 text-sm italic text-[var(--color-text-muted)]">
          No existing systems match "{query}" — it will be created as a new system.
        </div>
      ) : null}
      <p className="mt-2 text-xs text-slate-500">
        {description ?? (loading ? "Loading known systems…" : "Type a new system name or reuse an existing one.")}
      </p>
    </label>
  );
}
