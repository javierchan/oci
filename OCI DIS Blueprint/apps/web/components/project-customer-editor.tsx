"use client";

import { Check, Pencil, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { emitToast } from "@/hooks/use-toast";
import { api } from "@/lib/api";

type ProjectCustomerEditorProps = {
  projectId: string;
  customerName: string;
};

export function ProjectCustomerEditor({
  projectId,
  customerName,
}: ProjectCustomerEditorProps): JSX.Element {
  const router = useRouter();
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(customerName);
  const [saving, setSaving] = useState(false);

  async function save(): Promise<void> {
    const normalized = value.trim();
    if (!normalized) {
      emitToast("error", "Customer name is required.");
      return;
    }
    if (normalized === customerName) {
      setEditing(false);
      return;
    }

    setSaving(true);
    try {
      await api.updateProject(projectId, { customer_name: normalized });
      emitToast("success", "Customer name updated.");
      setEditing(false);
      router.refresh();
    } catch (error) {
      emitToast(
        "error",
        error instanceof Error ? error.message : "Unable to update the customer name.",
      );
    } finally {
      setSaving(false);
    }
  }

  if (!editing) {
    return (
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <span className="app-label">Customer</span>
        <span className="text-sm font-semibold text-[var(--color-text-primary)]">
          {customerName}
        </span>
        <button
          type="button"
          onClick={() => setEditing(true)}
          className="app-icon-button h-8 w-8"
          title="Edit customer name"
          aria-label="Edit customer name"
        >
          <Pencil className="h-3.5 w-3.5" />
        </button>
      </div>
    );
  }

  return (
    <div className="mt-3 flex max-w-2xl flex-wrap items-end gap-2">
      <label className="min-w-[16rem] flex-1">
        <span className="app-label">Customer</span>
        <input
          autoFocus
          value={value}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              void save();
            }
            if (event.key === "Escape") {
              setValue(customerName);
              setEditing(false);
            }
          }}
          className="app-input mt-2 py-2"
          aria-label="Customer name"
        />
      </label>
      <button
        type="button"
        onClick={() => void save()}
        disabled={saving}
        className="app-icon-button h-10 w-10 text-[var(--color-success)]"
        title="Save customer name"
        aria-label="Save customer name"
      >
        <Check className="h-4 w-4" />
      </button>
      <button
        type="button"
        onClick={() => {
          setValue(customerName);
          setEditing(false);
        }}
        disabled={saving}
        className="app-icon-button h-10 w-10"
        title="Cancel editing"
        aria-label="Cancel editing"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}
