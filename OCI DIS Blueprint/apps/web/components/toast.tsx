"use client";

import { CheckCircle, Info, X, XCircle } from "lucide-react";

import { useToastStack } from "@/hooks/use-toast";
import type { Toast, ToastKind } from "@/hooks/use-toast";

const KIND_STYLES: Record<ToastKind, { wrapper: string; icon: JSX.Element }> = {
  success: {
    wrapper:
      "border-[var(--color-toast-success-border)] bg-[var(--color-toast-success-bg)] text-[var(--color-toast-success-text)]",
    icon: <CheckCircle className="h-4 w-4 shrink-0" />,
  },
  error: {
    wrapper:
      "border-[var(--color-toast-error-border)] bg-[var(--color-toast-error-bg)] text-[var(--color-toast-error-text)]",
    icon: <XCircle className="h-4 w-4 shrink-0" />,
  },
  info: {
    wrapper:
      "border-[var(--color-toast-info-border)] bg-[var(--color-toast-info-bg)] text-[var(--color-toast-info-text)]",
    icon: <Info className="h-4 w-4 shrink-0" />,
  },
};

function ToastItem({
  toast,
  onDismiss,
}: {
  toast: Toast;
  onDismiss: (_toastId: string) => void;
}): JSX.Element {
  const { wrapper, icon } = KIND_STYLES[toast.kind];
  return (
    <div
      role="alert"
      className={`toast-${toast.exiting ? "exit" : "enter"} flex items-start gap-3 rounded-2xl border px-4 py-3 text-sm font-medium shadow-lg ${wrapper}`}
    >
      {icon}
      <span className="flex-1">{toast.message}</span>
      <button
        type="button"
        onClick={() => onDismiss(toast.id)}
        className="ml-1 transition-opacity hover:opacity-100 opacity-60"
        aria-label="Dismiss"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}

export function ToastStack(): JSX.Element {
  const { toasts, dismiss } = useToastStack();
  if (toasts.length === 0) {
    return <></>;
  }

  return (
    <div className="fixed bottom-6 right-6 z-50 flex w-80 max-w-[calc(100vw-3rem)] flex-col gap-2">
      {toasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} onDismiss={dismiss} />
      ))}
    </div>
  );
}
