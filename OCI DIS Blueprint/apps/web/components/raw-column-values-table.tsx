"use client";

/* Inline editor for source-lineage raw column values on the integration detail page. */

import { Check, Pencil } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { api } from "@/lib/api";
import { displaySourceFieldLabel, displayUiValue } from "@/lib/format";
import { TruncatedCell } from "@/components/truncated-cell";

type RawColumnValuesTableProps = {
  projectId: string;
  integrationId: string;
  initialValues: Record<string, unknown>;
  columnNames: Record<string, string>;
};

function stringifyValue(value: unknown): string {
  if (value === null || value === undefined) {
    return "";
  }
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return JSON.stringify(value);
}

function displayValue(value: unknown): { primary: string; source: string | null } {
  const source = stringifyValue(value);
  if (typeof value !== "string") {
    return {
      primary: source || "—",
      source: null,
    };
  }

  const translated = displayUiValue(value);
  return {
    primary: translated || "—",
    source: translated !== value ? value : null,
  };
}

function hasVisibleValue(value: unknown): boolean {
  if (value === null || value === undefined) {
    return false;
  }
  if (typeof value === "string") {
    return value.trim() !== "";
  }
  return true;
}

function compareLineageKeys(left: string, right: string): number {
  const leftIsNumeric = /^\d+$/.test(left);
  const rightIsNumeric = /^\d+$/.test(right);
  if (leftIsNumeric && rightIsNumeric) {
    return Number(left) - Number(right);
  }
  if (leftIsNumeric) {
    return -1;
  }
  if (rightIsNumeric) {
    return 1;
  }
  return left.localeCompare(right);
}

function displayFieldLabel(fieldKey: string, columnNames: Record<string, string>): string {
  return displaySourceFieldLabel(columnNames[fieldKey] ?? fieldKey);
}

function isUnnamedColumn(label: string): boolean {
  return /^Column \d+$/.test(label);
}

export function RawColumnValuesTable({
  projectId,
  integrationId,
  initialValues,
  columnNames,
}: RawColumnValuesTableProps): JSX.Element {
  const router = useRouter();
  const [values, setValues] = useState<Record<string, unknown>>(initialValues);
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [draftValue, setDraftValue] = useState<string>("");
  const [savingKey, setSavingKey] = useState<string | null>(null);
  const [toastVisible, setToastVisible] = useState<boolean>(false);
  const [error, setError] = useState<string>("");

  const lineageEntries = Object.entries(values).sort(([left], [right]) => compareLineageKeys(left, right));
  const populatedEntries = lineageEntries.filter(([, value]) => hasVisibleValue(value));
  const hiddenEntries = lineageEntries.filter(([, value]) => !hasVisibleValue(value));

  function beginEdit(fieldKey: string): void {
    setEditingKey(fieldKey);
    setDraftValue(stringifyValue(values[fieldKey]));
    setError("");
  }

  function cancelEdit(): void {
    setEditingKey(null);
    setDraftValue("");
    setError("");
  }

  async function saveEdit(fieldKey: string): Promise<void> {
    if (savingKey) {
      return;
    }

    const nextValues = {
      ...values,
      [fieldKey]: draftValue,
    };

    setSavingKey(fieldKey);
    setError("");
    try {
      await api.patchIntegration(projectId, integrationId, {
        raw_column_values: nextValues,
      });
      setValues(nextValues);
      setEditingKey(null);
      setDraftValue("");
      setToastVisible(true);
      window.setTimeout(() => setToastVisible(false), 1400);
      window.setTimeout(() => router.refresh(), 200);
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Unable to save raw column value.");
    } finally {
      setSavingKey(null);
    }
  }

  function renderFieldCell(fieldKey: string): JSX.Element {
    const label = displayFieldLabel(fieldKey, columnNames);
    const sourceLabel = columnNames[fieldKey] ?? fieldKey;
    const unnamed = isUnnamedColumn(label);
    const title = unnamed
      ? "Header not recognized — rename in source file"
      : label !== sourceLabel
        ? `Original source column: ${sourceLabel}`
        : undefined;
    return (
      <td
        className={[
          "px-4 py-3 font-medium",
          unnamed
            ? "italic text-[var(--color-text-muted)]"
            : "text-[var(--color-text-primary)]",
        ].join(" ")}
        title={title}
      >
        {label}
      </td>
    );
  }

  function renderValueCell(fieldKey: string, value: unknown): JSX.Element {
    const isEditing = editingKey === fieldKey;
    const formattedValue = displayValue(value);
    return (
      <td className="group px-4 py-3 text-[var(--color-text-secondary)]">
        {isEditing ? (
          <input
            autoFocus
            value={draftValue}
            onChange={(event) => setDraftValue(event.target.value)}
            onBlur={() => {
              void saveEdit(fieldKey);
            }}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                void saveEdit(fieldKey);
              }
              if (event.key === "Escape") {
                event.preventDefault();
                cancelEdit();
              }
            }}
            className="w-full rounded-xl border border-[var(--color-border)] px-3 py-2 text-sm"
          />
        ) : (
          <div className="flex items-start justify-between gap-3">
            <div
              className="min-w-0 flex-1 break-words"
              title={formattedValue.source ? `Original source value: ${formattedValue.source}` : undefined}
            >
              <TruncatedCell value={formattedValue.primary} />
            </div>
            <button
              type="button"
              onClick={() => beginEdit(fieldKey)}
              className="shrink-0 opacity-0 transition group-hover:opacity-100"
              title="Edit source value"
            >
              <Pencil className="h-4 w-4 text-[var(--color-text-muted)]" />
            </button>
          </div>
        )}
      </td>
    );
  }

  function renderRows(entries: Array<[string, unknown]>): JSX.Element[] {
    return entries.map(([fieldKey, value]) => (
      <tr key={fieldKey} className="app-table-row">
        {renderFieldCell(fieldKey)}
        {renderValueCell(fieldKey, value)}
      </tr>
    ));
  }

  return (
    <div className="relative">
      <div className="mt-4 overflow-hidden rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)]">
        <table className="min-w-full divide-y divide-[var(--color-table-border)] text-left">
          <thead className="app-table-header">
            <tr>
              <th className="px-4 py-3">Field</th>
              <th className="px-4 py-3">Source Value</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--color-table-border)] text-sm">
            {renderRows(populatedEntries)}
          </tbody>
        </table>
      </div>

      {hiddenEntries.length > 0 ? (
        <details className="mt-4 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)]">
          <summary className="cursor-pointer px-4 py-3 text-sm font-medium text-[var(--color-accent)]">
            Show all columns ({hiddenEntries.length})
          </summary>
          <div className="border-t border-[var(--color-border)]">
            <table className="min-w-full divide-y divide-[var(--color-table-border)] text-left">
              <tbody className="divide-y divide-[var(--color-table-border)] text-sm">
                {renderRows(hiddenEntries)}
              </tbody>
            </table>
          </div>
        </details>
      ) : null}

      {toastVisible ? (
        <div className="pointer-events-none absolute right-3 top-3 inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700 shadow-sm">
          <Check className="h-3.5 w-3.5" />
          Saved
        </div>
      ) : null}

      {savingKey ? (
        <p className="mt-3 text-xs text-[var(--color-text-muted)]">Saving raw column override…</p>
      ) : null}
      {error ? <p className="mt-3 text-sm text-rose-600">{error}</p> : null}
    </div>
  );
}
