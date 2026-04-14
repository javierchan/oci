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
        .filter((system) => system.toLowerCase().includes(value.trim().toLowerCase()))
        .slice(0, 8),
    [systems, value],
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
          className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-950 outline-none focus:border-sky-400"
        />
        {focused && suggestions.length > 0 ? (
          <div className="absolute z-10 mt-2 w-full overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-xl">
            {suggestions.map((system) => (
              <button
                key={system}
                type="button"
                onMouseDown={() => onChange(system)}
                className="block w-full px-4 py-3 text-left text-sm text-slate-700 transition hover:bg-sky-50 hover:text-slate-950"
              >
                {system}
              </button>
            ))}
          </div>
        ) : null}
      </div>
      <p className="mt-2 text-xs text-slate-500">
        {description ?? (loading ? "Loading known systems…" : "Type a new system name or reuse an existing one.")}
      </p>
    </label>
  );
}
