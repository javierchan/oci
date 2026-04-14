"use client";

/* Reusable confirmation dialog for destructive admin governance actions. */

import * as Dialog from "@radix-ui/react-dialog";
import { AlertTriangle } from "lucide-react";
import type { ReactNode } from "react";

type AdminConfirmDeleteProps = {
  open: boolean;
  title: string;
  description: string;
  onConfirm: () => void | Promise<void>;
  onCancel: () => void;
  isLoading: boolean;
  children?: ReactNode;
};

export function AdminConfirmDelete({
  open,
  title,
  description,
  onConfirm,
  onCancel,
  isLoading,
  children,
}: AdminConfirmDeleteProps): JSX.Element {
  return (
    <Dialog.Root open={open} onOpenChange={(nextOpen) => (!nextOpen ? onCancel() : undefined)}>
      {children ? <Dialog.Trigger asChild>{children}</Dialog.Trigger> : null}
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-slate-950/60 backdrop-blur-sm" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-[min(92vw,32rem)] -translate-x-1/2 -translate-y-1/2 rounded-[2rem] border border-rose-200 bg-[var(--color-surface)] p-6 shadow-2xl">
          <div className="flex items-start gap-4">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-rose-100 text-rose-700">
              <AlertTriangle className="h-6 w-6" />
            </div>
            <div className="flex-1">
              <Dialog.Title className="text-xl font-semibold text-[var(--color-text-primary)]">{title}</Dialog.Title>
              <Dialog.Description className="mt-3 text-sm leading-6 text-[var(--color-text-secondary)]">
                {description}
              </Dialog.Description>
            </div>
          </div>

          <div className="mt-6 flex flex-wrap justify-end gap-3">
            <button
              type="button"
              onClick={onCancel}
              disabled={isLoading}
              className="app-button-secondary"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={() => {
                void onConfirm();
              }}
              disabled={isLoading}
              className="rounded-full bg-rose-600 px-5 py-3 text-sm font-semibold text-white transition hover:bg-rose-500 disabled:cursor-not-allowed disabled:bg-rose-300"
            >
              {isLoading ? "Deleting…" : "Delete"}
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
