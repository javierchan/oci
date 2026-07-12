"use client";

/* Accessible searchable listbox used by the topology workspace filters. */

import { Check, ChevronDown, Search, X } from "lucide-react";
import { useEffect, useId, useMemo, useRef, useState } from "react";

type TopologyComboboxProps = {
  label: string;
  ariaLabel: string;
  value: string;
  options: string[];
  placeholder: string;
  onChange: (_value: string) => void;
};

const MAX_VISIBLE_OPTIONS = 10;

export function TopologyCombobox({
  label,
  ariaLabel,
  value,
  options,
  placeholder,
  onChange,
}: TopologyComboboxProps): JSX.Element {
  const listId = useId();
  const containerRef = useRef<HTMLDivElement>(null);
  const [draft, setDraft] = useState(value);
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);

  useEffect(() => setDraft(value), [value]);

  useEffect(() => {
    function handlePointerDown(event: PointerEvent): void {
      if (!containerRef.current?.contains(event.target as Node)) {
        setDraft(value);
        setOpen(false);
      }
    }

    document.addEventListener("pointerdown", handlePointerDown);
    return () => document.removeEventListener("pointerdown", handlePointerDown);
  }, [value]);

  const filteredOptions = useMemo(() => {
    const normalized = draft.trim().toLowerCase();
    const matches = normalized
      ? options.filter((option) => option.toLowerCase().includes(normalized))
      : options;
    return matches.slice(0, MAX_VISIBLE_OPTIONS);
  }, [draft, options]);

  useEffect(() => {
    setActiveIndex((current) => Math.min(current, Math.max(filteredOptions.length - 1, 0)));
  }, [filteredOptions.length]);

  function selectOption(option: string): void {
    setDraft(option);
    setOpen(false);
    setActiveIndex(0);
    onChange(option);
  }

  function clearSelection(): void {
    setDraft("");
    setOpen(false);
    setActiveIndex(0);
    onChange("");
  }

  const activeOptionId = open && filteredOptions[activeIndex]
    ? `${listId}-option-${activeIndex}`
    : undefined;

  return (
    <div ref={containerRef} className="relative min-w-0">
      <div className="flex min-h-10 min-w-0 items-center gap-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 text-xs text-[var(--color-text-secondary)] focus-within:border-[var(--color-line-strong)] focus-within:ring-1 focus-within:ring-[var(--color-line-strong)]">
        <span className="shrink-0 font-semibold">{label}</span>
        <Search className="h-3.5 w-3.5 shrink-0 text-[var(--color-text-muted)]" />
        <input
          value={draft}
          onChange={(event) => {
            setDraft(event.target.value);
            setOpen(true);
            setActiveIndex(0);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={(event) => {
            if (event.key === "ArrowDown") {
              event.preventDefault();
              setOpen(true);
              setActiveIndex((current) => Math.min(current + 1, Math.max(filteredOptions.length - 1, 0)));
            }
            if (event.key === "ArrowUp") {
              event.preventDefault();
              setOpen(true);
              setActiveIndex((current) => Math.max(current - 1, 0));
            }
            if (event.key === "Enter") {
              event.preventDefault();
              const option = filteredOptions[activeIndex];
              if (open && option) {
                selectOption(option);
              } else if (!draft.trim()) {
                clearSelection();
              }
            }
            if (event.key === "Escape") {
              setDraft(value);
              setOpen(false);
            }
          }}
          role="combobox"
          aria-label={ariaLabel}
          aria-autocomplete="list"
          aria-controls={listId}
          aria-expanded={open}
          aria-activedescendant={activeOptionId}
          placeholder={placeholder}
          className="min-w-20 flex-1 bg-transparent py-2 font-semibold text-[var(--color-text-primary)] outline-none placeholder:text-[var(--color-text-muted)]"
        />
        {value || draft ? (
          <button
            type="button"
            onClick={clearSelection}
            className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md hover:bg-[var(--color-hover)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
            aria-label={`Clear ${ariaLabel.toLowerCase()}`}
          >
            <X className="h-3.5 w-3.5" />
          </button>
        ) : (
          <button
            type="button"
            onClick={() => setOpen((current) => !current)}
            className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md hover:bg-[var(--color-hover)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
            aria-label={`Show ${label.toLowerCase()} options`}
            aria-expanded={open}
            aria-controls={listId}
          >
            <ChevronDown className={`h-3.5 w-3.5 transition ${open ? "rotate-180" : ""}`} />
          </button>
        )}
      </div>

      {open ? (
        <div
          id={listId}
          role="listbox"
          aria-label={`${label} options`}
          className="absolute left-0 right-0 top-[calc(100%+0.35rem)] z-50 max-h-72 overflow-y-auto rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-1.5 shadow-xl"
        >
          {filteredOptions.map((option, index) => (
            <button
              key={option}
              id={`${listId}-option-${index}`}
              type="button"
              role="option"
              aria-selected={option === value}
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => selectOption(option)}
              onMouseEnter={() => setActiveIndex(index)}
              className={`flex w-full items-center justify-between gap-3 rounded-md px-3 py-2 text-left text-sm transition ${
                index === activeIndex
                  ? "bg-[var(--color-hover)] text-[var(--color-text-primary)]"
                  : "text-[var(--color-text-secondary)]"
              }`}
            >
              <span className="truncate" title={option}>{option}</span>
              {option === value ? <Check className="h-4 w-4 shrink-0 text-[var(--color-accent)]" /> : null}
            </button>
          ))}
          {filteredOptions.length === 0 ? (
            <p className="px-3 py-3 text-sm text-[var(--color-text-muted)]">
              No matching option. Clear the text or choose another value.
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
