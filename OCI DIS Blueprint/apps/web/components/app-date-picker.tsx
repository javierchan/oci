"use client";

/* Theme-aware single-date picker for governed App forms. */

import { CalendarDays, ChevronLeft, ChevronRight } from "lucide-react";
import { useEffect, useId, useMemo, useRef, useState } from "react";

export type CalendarDay = {
  date: Date;
  iso: string;
  day: number;
  inCurrentMonth: boolean;
  isToday: boolean;
};

export function toIsoDate(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function parseIsoDate(value: string): Date | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return null;
  const date = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
  return toIsoDate(date) === value ? date : null;
}

export function buildCalendarDays(month: Date, today = new Date()): CalendarDay[] {
  const firstOfMonth = new Date(month.getFullYear(), month.getMonth(), 1);
  const gridStart = new Date(firstOfMonth);
  gridStart.setDate(gridStart.getDate() - firstOfMonth.getDay());
  const todayIso = toIsoDate(today);

  return Array.from({ length: 42 }, (_, index) => {
    const date = new Date(gridStart);
    date.setDate(gridStart.getDate() + index);
    const iso = toIsoDate(date);
    return {
      date,
      iso,
      day: date.getDate(),
      inCurrentMonth: date.getMonth() === month.getMonth(),
      isToday: iso === todayIso,
    };
  });
}

function addDays(date: Date, count: number): Date {
  const next = new Date(date);
  next.setDate(next.getDate() + count);
  return next;
}

function addMonths(date: Date, count: number): Date {
  return new Date(date.getFullYear(), date.getMonth() + count, 1);
}

function dateLabel(value: string): string {
  const date = parseIsoDate(value);
  if (!date) return "Choose date";
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(date);
}

export function AppDatePicker({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (_value: string) => void;
}): JSX.Element {
  const selectedDate = parseIsoDate(value);
  const today = useMemo(() => new Date(), []);
  const [open, setOpen] = useState(false);
  const [visibleMonth, setVisibleMonth] = useState<Date>(selectedDate ?? today);
  const [pendingFocusIso, setPendingFocusIso] = useState<string | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const calendarRef = useRef<HTMLDivElement>(null);
  const labelId = useId();
  const valueId = useId();
  const dialogId = useId();

  const days = useMemo(() => buildCalendarDays(visibleMonth, today), [today, visibleMonth]);
  const visibleMonthLabel = new Intl.DateTimeFormat("en-US", {
    month: "long",
    year: "numeric",
  }).format(visibleMonth);
  const firstCurrentMonthDay = days.find((day) => day.inCurrentMonth)?.iso ?? days[0]?.iso;
  const selectedInVisibleMonth = selectedDate
    && selectedDate.getFullYear() === visibleMonth.getFullYear()
    && selectedDate.getMonth() === visibleMonth.getMonth();
  const rovingIso = selectedInVisibleMonth ? value : firstCurrentMonthDay;

  useEffect(() => {
    if (!open) return undefined;

    function closeOnOutsidePointer(event: PointerEvent): void {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    }

    function closeOnEscape(event: KeyboardEvent): void {
      if (event.key === "Escape") {
        setOpen(false);
        triggerRef.current?.focus();
      }
    }

    document.addEventListener("pointerdown", closeOnOutsidePointer);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("pointerdown", closeOnOutsidePointer);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [open]);

  useEffect(() => {
    if (!open || !pendingFocusIso) return;
    const button = calendarRef.current?.querySelector<HTMLButtonElement>(`[data-date="${pendingFocusIso}"]`);
    if (button) {
      button.focus();
      setPendingFocusIso(null);
    }
  }, [days, open, pendingFocusIso]);

  function openCalendar(): void {
    const initialDate = selectedDate ?? today;
    setVisibleMonth(initialDate);
    setPendingFocusIso(toIsoDate(initialDate));
    setOpen(true);
  }

  function selectDate(date: Date): void {
    onChange(toIsoDate(date));
    setOpen(false);
    triggerRef.current?.focus();
  }

  function moveFocus(date: Date): void {
    setVisibleMonth(new Date(date.getFullYear(), date.getMonth(), 1));
    setPendingFocusIso(toIsoDate(date));
  }

  function handleDayKeyDown(event: React.KeyboardEvent<HTMLButtonElement>, date: Date): void {
    let target: Date | null = null;
    if (event.key === "ArrowLeft") target = addDays(date, -1);
    if (event.key === "ArrowRight") target = addDays(date, 1);
    if (event.key === "ArrowUp") target = addDays(date, -7);
    if (event.key === "ArrowDown") target = addDays(date, 7);
    if (event.key === "Home") target = addDays(date, -date.getDay());
    if (event.key === "End") target = addDays(date, 6 - date.getDay());
    if (event.key === "PageUp") target = addMonths(date, -1);
    if (event.key === "PageDown") target = addMonths(date, 1);
    if (!target) return;
    event.preventDefault();
    moveFocus(target);
  }

  return (
    <div ref={rootRef} className="relative min-w-0 text-sm font-semibold text-[var(--color-text-primary)]">
      <span id={labelId}>{label}</span>
      <button
        ref={triggerRef}
        type="button"
        aria-labelledby={`${labelId} ${valueId}`}
        aria-haspopup="dialog"
        aria-controls={dialogId}
        aria-expanded={open}
        className="mt-2 flex h-[46px] w-full items-center justify-between gap-3 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 text-left font-medium text-[var(--color-text-primary)] shadow-sm transition hover:border-[var(--color-accent-border)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)]"
        onClick={() => open ? setOpen(false) : openCalendar()}
      >
        <span id={valueId}>{dateLabel(value)}</span>
        <CalendarDays className="h-4 w-4 shrink-0 text-[var(--color-text-muted)]" />
      </button>

      {open ? (
        <div
          id={dialogId}
          ref={calendarRef}
          role="dialog"
          aria-modal="false"
          aria-label={`${label} calendar`}
          className="fixed inset-x-4 top-1/2 z-[80] w-auto -translate-y-1/2 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-3 text-[var(--color-text-primary)] shadow-[0_18px_50px_rgba(0,0,0,0.22)] sm:absolute sm:inset-x-auto sm:right-0 sm:top-full sm:z-50 sm:mt-2 sm:w-80 sm:translate-y-0"
        >
          <div className="flex items-center justify-between gap-2">
            <button
              type="button"
              aria-label="Previous month"
              title="Previous month"
              className="flex h-9 w-9 items-center justify-center rounded-lg text-[var(--color-text-secondary)] transition hover:bg-[var(--color-surface-2)] hover:text-[var(--color-text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)]"
              onClick={() => setVisibleMonth((current) => addMonths(current, -1))}
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <p aria-live="polite" className="text-sm font-semibold">{visibleMonthLabel}</p>
            <button
              type="button"
              aria-label="Next month"
              title="Next month"
              className="flex h-9 w-9 items-center justify-center rounded-lg text-[var(--color-text-secondary)] transition hover:bg-[var(--color-surface-2)] hover:text-[var(--color-text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)]"
              onClick={() => setVisibleMonth((current) => addMonths(current, 1))}
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>

          <div className="mt-2 grid grid-cols-7" aria-hidden="true">
            {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((weekday) => (
              <span key={weekday} className="flex h-8 items-center justify-center text-[10px] font-semibold uppercase text-[var(--color-text-muted)]">
                {weekday.slice(0, 2)}
              </span>
            ))}
          </div>

          <div role="grid" aria-label={visibleMonthLabel} className="grid grid-cols-7 gap-1">
            {days.map((day) => {
              const selected = day.iso === value;
              return (
                <button
                  key={day.iso}
                  type="button"
                  role="gridcell"
                  data-date={day.iso}
                  aria-label={new Intl.DateTimeFormat("en-US", { dateStyle: "full" }).format(day.date)}
                  aria-selected={selected}
                  tabIndex={day.iso === rovingIso ? 0 : -1}
                  className={`relative flex aspect-square min-h-9 items-center justify-center rounded-lg text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)] ${selected ? "bg-[var(--color-accent)] text-white shadow-sm" : day.inCurrentMonth ? "text-[var(--color-text-primary)] hover:bg-[var(--color-surface-2)]" : "text-[var(--color-text-muted)] opacity-55 hover:bg-[var(--color-surface-2)]"} ${day.isToday && !selected ? "ring-1 ring-inset ring-[var(--color-accent-border)]" : ""}`}
                  onClick={() => selectDate(day.date)}
                  onKeyDown={(event) => handleDayKeyDown(event, day.date)}
                >
                  {day.day}
                </button>
              );
            })}
          </div>

          <div className="mt-3 flex items-center justify-between border-t border-[var(--color-border)] pt-3">
            <p className="text-xs font-normal text-[var(--color-text-muted)]">Contract month 1</p>
            <button
              type="button"
              className="rounded-lg px-3 py-2 text-xs font-semibold text-[var(--color-accent)] transition hover:bg-[var(--color-accent-soft)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)]"
              onClick={() => selectDate(today)}
            >
              Today
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
